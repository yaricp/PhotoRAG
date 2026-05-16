import { ipcMain, dialog, app, WebContents } from 'electron'
import { existsSync, writeFileSync } from 'fs'
import { join } from 'path'
import { spawn } from 'child_process'
import { locatePython, locateBackend } from './backend'

export function registerIpcHandlers(backendPort: number): void {
    console.log('[IPC] registering handlers, port =', backendPort)

    ipcMain.handle('select-folder', async () => {
        const result = await dialog.showOpenDialog({
            properties: ['openDirectory'],
            title: 'Select Photos Folder',
        })
        return result.canceled ? null : result.filePaths[0]
    })

    ipcMain.handle('get-backend-port', () => backendPort)

    // Check whether first-run setup wizard is needed (venv not yet created).
    ipcMain.handle('setup:check-needed', () => {
        const venvPath = join(app.getPath('userData'), 'venv')
        return { needed: !existsSync(venvPath) }
    })

    // Install Python deps into userData/venv and stream progress back.
    ipcMain.handle('setup:install-deps', async (event) => {
        const userData = app.getPath('userData')
        const venvPath = join(userData, 'venv')
        const python = locatePython()
        const backend = locateBackend()

        // Step 1: create venv (~5% progress)
        await spawnTracked(python, ['-m', 'venv', venvPath], {}, (line) => {
            event.sender.send('setup:install-deps-progress', { line, percent: 5 })
        })

        // Step 2: pip install requirements (5→95%)
        const pip = join(venvPath, 'bin', 'pip')
        const requirements = join(backend, 'requirements.txt')
        let lineCount = 0
        await spawnTracked(pip, ['install', '-r', requirements, '--progress-bar', 'off'], {}, (line) => {
            lineCount++
            const percent = Math.min(95, 5 + lineCount * 0.5)
            event.sender.send('setup:install-deps-progress', { line, percent })
        })

        event.sender.send('setup:install-deps-progress', { line: 'Done.', percent: 100 })
    })

    // Run full_install.py to initialise the database.
    ipcMain.handle('setup:init-db', async () => {
        const userData = app.getPath('userData')
        const venvPath = join(userData, 'venv')
        const python = join(venvPath, 'bin', 'python3')
        const backend = locateBackend()
        await spawnTracked(python, ['full_install.py'], { cwd: backend })
    })

    // Download a single model.
    ipcMain.handle('setup:download-model', async (event, { modelId }: { modelId: string }) => {
        const userData = app.getPath('userData')
        const venvPath = join(userData, 'venv')
        const python = join(venvPath, 'bin', 'python3')
        const backend = locateBackend()

        activeDownload = spawnTracked(
            python,
            ['-c', buildDownloadScript(modelId, userData)],
            { cwd: backend },
            (line) => {
                const m = line.match(/PROGRESS:(\d+(?:\.\d+)?):(\d+)/)
                if (m) {
                    const percent = parseFloat(m[1])
                    const bytes = parseInt(m[2], 10)
                    event.sender.send('setup:download-model-progress', { modelId, percent, bytes })
                }
            }
        )
        await activeDownload
        activeDownload = null
    })

    // Cancel current download.
    ipcMain.handle('setup:cancel-download', () => {
        if (activeDownload) {
            activeDownload.cancel?.()
            activeDownload = null
        }
    })

    // Write marker file and env stubs, then the renderer will reload as main app.
    ipcMain.handle('setup:complete', (_, payload?: { skippedModels?: string[] }) => {
        const userData = app.getPath('userData')
        writeFileSync(join(userData, 'setup_done'), new Date().toISOString())

        const skipped = new Set(payload?.skippedModels ?? [])
        const envLines: string[] = []
        if (skipped.has('vision'))      envLines.push('VISION_MODE=remote')
        if (skipped.has('translation')) envLines.push('TRANSLATION_MODE=remote')
        if (skipped.has('ocr'))         envLines.push('OCR_MODE=remote')
        if (skipped.has('chat'))        envLines.push('CHAT_MODE=remote')

        if (envLines.length > 0) {
            const envPath = join(userData, '.env')
            const existing = existsSync(envPath) ? require('fs').readFileSync(envPath, 'utf8') : ''
            const toAppend = envLines.filter(l => !existing.includes(l.split('=')[0]))
            if (toAppend.length > 0) {
                writeFileSync(envPath, existing + '\n' + toAppend.join('\n') + '\n')
            }
        }
    })

    console.log('[IPC] done')
}

// Tracks the current download so it can be cancelled.
let activeDownload: (Promise<void> & { cancel?: () => void }) | null = null

// Spawns a process, collects stdout/stderr line-by-line, rejects on non-zero exit.
function spawnTracked(
    cmd: string,
    args: string[],
    opts: { cwd?: string; env?: NodeJS.ProcessEnv },
    onLine?: (line: string) => void
): Promise<void> & { cancel?: () => void } {
    let resolveFn: () => void
    let rejectFn: (e: Error) => void
    const promise = new Promise<void>((res, rej) => {
        resolveFn = res
        rejectFn = rej
    })

    const child = spawn(cmd, args, {
        cwd: opts.cwd,
        env: opts.env ?? process.env,
    })

    let buf = ''
    const handleData = (data: Buffer) => {
        buf += data.toString()
        const lines = buf.split('\n')
        buf = lines.pop() ?? ''
        lines.forEach(line => onLine?.(line))
    }
    child.stdout?.on('data', handleData)
    child.stderr?.on('data', handleData)

    child.on('close', (code) => {
        if (buf) onLine?.(buf)
        if (code === 0) resolveFn!()
        else rejectFn!(new Error(`Process exited with code ${code}`))
    })
    child.on('error', (e) => rejectFn!(e))

    const cancellable = promise as Promise<void> & { cancel?: () => void }
    cancellable.cancel = () => { child.kill('SIGTERM') }
    return cancellable
}

function buildDownloadScript(modelId: string, userData: string): string {
    return `
import sys, os
sys.path.insert(0, '.')
os.environ.setdefault('APP_DATA_DIR', ${JSON.stringify(userData)})
from src.download import download_model
download_model(${JSON.stringify(modelId)})
`
}
