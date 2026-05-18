import { ipcMain, dialog, shell, app, WebContents } from 'electron'
import { existsSync, writeFileSync, readFileSync, rmSync } from 'fs'
import { join } from 'path'
import { spawn } from 'child_process'
import { locatePython, locateBackend, startBackend, waitForBackend } from './backend'

// Mutable so setup:complete can update it after starting the backend.
let currentPort = 0

export function registerIpcHandlers(port: number): void {
    currentPort = port
    console.log('[IPC] registering handlers, port =', port)

    ipcMain.handle('select-folder', async () => {
        const result = await dialog.showOpenDialog({
            properties: ['openDirectory'],
            title: 'Select Photos Folder',
        })
        return result.canceled ? null : result.filePaths[0]
    })

    ipcMain.handle('get-backend-port', () => currentPort)

    // Check whether first-run setup wizard is needed.
    ipcMain.handle('setup:check-needed', () => {
        const done = existsSync(join(app.getPath('userData'), 'setup_done'))
        return { needed: !done }
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

    // Initialise the database schema only. Model downloads happen in the
    // separate download step so they go to the correct HF cache path.
    ipcMain.handle('setup:init-db', async () => {
        const userData = app.getPath('userData')
        const venvPath = join(userData, 'venv')
        const python = join(venvPath, 'bin', 'python3')
        const backend = locateBackend()
        await spawnTracked(python, ['init_db_only.py'], {
            cwd: backend,
            env: {
                ...process.env,
                APP_DATA_DIR: userData,
                QUEUE_DB_DIR: userData,
                HUGGINGFACE_HUB_CACHE: join(userData, '.hf_cache'),
            },
        })
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
            {
                cwd: backend,
                env: {
                    ...process.env,
                    APP_DATA_DIR: userData,
                    QUEUE_DB_DIR: userData,
                    HUGGINGFACE_HUB_CACHE: join(userData, '.hf_cache'),
                },
            },
            (line) => {
                const m = line.match(/PROGRESS:(\d+(?:\.\d+)?):(\d+)/)
                if (m) {
                    const percent = parseFloat(m[1])
                    const bytes = parseInt(m[2], 10)
                    console.log(`[progress:${modelId}] ${percent.toFixed(1)}% ${bytes}B`)
                    event.sender.send('setup:download-model-progress', { modelId, percent, bytes })
                } else if (line.trim()) {
                    console.log(`[download:${modelId}]`, line)
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

    // Write marker + env stubs, start the backend, then return so the renderer
    // can switch to app mode knowing the backend is ready.
    ipcMain.handle('setup:complete', async (_, payload?: { skippedModels?: string[] }) => {
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
            const existing = existsSync(envPath) ? readFileSync(envPath, 'utf8') : ''
            const toAppend = envLines.filter(l => !existing.includes(l.split('=')[0]))
            if (toAppend.length > 0) {
                writeFileSync(envPath, existing + '\n' + toAppend.join('\n') + '\n')
            }
        }

        // Start the backend now that venv and DB are ready.
        currentPort = await startBackend()
        await waitForBackend(currentPort)
    })

    // Full uninstall: remove all app data, move the .app to Trash, then quit.
    ipcMain.handle('app:uninstall', async () => {
        const { response } = await dialog.showMessageBox({
            type: 'warning',
            title: 'Uninstall PhotoRAG',
            message: 'Remove PhotoRAG completely?',
            detail: [
                'This will permanently delete:',
                '  • The application',
                '  • Your photo database and index',
                '  • Downloaded AI models (~several GB)',
                '  • Settings and setup data',
                '',
                'Your original photos are NOT affected.',
                'This cannot be undone.',
            ].join('\n'),
            buttons: ['Cancel', 'Uninstall'],
            defaultId: 0,
            cancelId: 0,
        })

        if (response !== 1) return { cancelled: true }

        // Remove userData (venv, DB, models, .env, setup_done, HF cache)
        const userData = app.getPath('userData')
        try {
            rmSync(userData, { recursive: true, force: true })
        } catch { /* ignore if already gone */ }

        // Move the .app bundle to Trash (works while app is running on macOS)
        if (app.isPackaged) {
            const appBundle = process.execPath.split('.app/Contents')[0] + '.app'
            try {
                await shell.trashItem(appBundle)
            } catch { /* ignore — user can drag to Trash manually */ }
        }

        app.quit()
        return { success: true }
    })

    // Read model configs from the DB (runs during setup, before backend starts).
    ipcMain.handle('setup:get-model-configs', async () => {
        const userData = app.getPath('userData')
        const venvPath = join(userData, 'venv')
        const python = join(venvPath, 'bin', 'python3')
        const backend = locateBackend()
        const script = `
import json, sys
sys.path.insert(0, '.')
from src.db.database import SessionLocal
from src.db_service import get_all_model_configs
db = SessionLocal()
try:
    configs = get_all_model_configs(db)
    print(json.dumps([{
        'id': c.id,
        'type': c.type,
        'mode': c.mode,
        'model_name': c.model_name or '',
        'url': c.url or '',
        'api_key': c.api_key or '',
        'model_provider': c.model_provider or '',
        'similarity_limit': c.similarity_limit,
    } for c in configs]))
finally:
    db.close()
`
        const output = await spawnCaptured(python, ['-c', script], {
            cwd: backend,
            env: { ...process.env, APP_DATA_DIR: userData, QUEUE_DB_DIR: userData, HUGGINGFACE_HUB_CACHE: join(userData, '.hf_cache') },
        })
        return JSON.parse(output.trim())
    })

    // Save model configs to the DB (runs during setup, before backend starts).
    ipcMain.handle('setup:save-model-configs', async (_, configs: any[]) => {
        const userData = app.getPath('userData')
        const venvPath = join(userData, 'venv')
        const python = join(venvPath, 'bin', 'python3')
        const backend = locateBackend()
        const script = `
import json, os, sys
sys.path.insert(0, '.')
from src.db.database import SessionLocal
from src.db_service import update_model_config
from src.schemas import AIModelConfigUpdate
configs = json.loads(os.environ['MODEL_CONFIGS'])
db = SessionLocal()
try:
    for c in configs:
        upd = AIModelConfigUpdate(
            mode=c['mode'],
            model_name=c.get('model_name') or '',
            url=c.get('url') or None,
            api_key=c.get('api_key') or None,
            model_provider=c.get('model_provider') or None,
            similarity_limit=c.get('similarity_limit'),
        )
        update_model_config(db, c['type'], upd)
finally:
    db.close()
print('OK')
`
        await spawnCaptured(python, ['-c', script], {
            cwd: backend,
            env: { ...process.env, APP_DATA_DIR: userData, QUEUE_DB_DIR: userData, HUGGINGFACE_HUB_CACHE: join(userData, '.hf_cache'), MODEL_CONFIGS: JSON.stringify(configs) },
        })
    })

    console.log('[IPC] done')
}

// Tracks the current download so it can be cancelled.
let activeDownload: (Promise<void> & { cancel?: () => void }) | null = null

// Runs a process and resolves with captured stdout, rejects on non-zero exit.
function spawnCaptured(
    cmd: string,
    args: string[],
    opts: { cwd?: string; env?: NodeJS.ProcessEnv }
): Promise<string> {
    return new Promise((resolve, reject) => {
        const child = spawn(cmd, args, {
            cwd: opts.cwd,
            env: opts.env ?? process.env,
        })
        let stdout = ''
        let stderr = ''
        child.stdout?.on('data', (d: Buffer) => { stdout += d.toString() })
        child.stderr?.on('data', (d: Buffer) => { stderr += d.toString() })
        child.on('close', (code) => {
            if (code === 0) resolve(stdout)
            else reject(new Error(`Process exited with code ${code}: ${stderr || stdout}`))
        })
        child.on('error', reject)
    })
}

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
    // Patch tqdm BEFORE importing any ML library so HuggingFace download
    // chunks emit real PROGRESS:<percent>:<bytes> lines to stdout.
    // disable=True silences tqdm's own stderr output; update() still
    // increments self.n (tqdm behaviour when disabled).
    return `
import sys, os, traceback
sys.path.insert(0, '.')

# Patch tqdm before any ML import so HF download progress is captured.
from tqdm import tqdm as _Orig

class _Reporter(_Orig):
    def __init__(self, *args, **kwargs):
        # Force enabled and redirect tqdm output to devnull.
        # Subclasses like hf_tqdm auto-set disable=True via isatty() when
        # running in a subprocess (no TTY). Disabled tqdm returns early from
        # __init__ without setting self.unit or incrementing self.n, which
        # breaks our update(). Forcing disable=False + devnull fixes both.
        kwargs['file'] = open(os.devnull, 'w')
        kwargs['disable'] = False
        super().__init__(*args, **kwargs)
    def update(self, n=1):
        super().update(n)  # increments self.n; writes to devnull
        if getattr(self, 'unit', None) == 'B' and getattr(self, 'total', None) and n:
            pct = min(99.0, self.n / self.total * 100)
            print(f'PROGRESS:{pct:.1f}:{int(self.n)}', flush=True)

import tqdm as _tm, tqdm.auto as _ta
_tm.tqdm = _ta.tqdm = _Reporter

print('PROGRESS:1:0', flush=True)

try:
    from src.install import (
        install_clip, install_embedding, install_vision,
        install_translator, install_ocr, install_chat,
    )
    from src.db.database import SessionLocal

    INSTALL_MAP = {
        'clip':        install_clip,
        'embedding':   install_embedding,
        'vision':      install_vision,
        'translation': install_translator,
        'ocr':         install_ocr,
        'chat':        install_chat,
    }

    model_id = ${JSON.stringify(modelId)}
    fn = INSTALL_MAP.get(model_id)
    if fn is None:
        print(f'ERROR: Unknown model id: {model_id}', flush=True)
        sys.exit(1)

    db = SessionLocal()
    try:
        fn(db)
    finally:
        db.close()

except Exception:
    print('ERROR: ' + traceback.format_exc(), flush=True)
    sys.exit(1)
`
}
