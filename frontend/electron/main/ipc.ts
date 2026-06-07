import { ipcMain, dialog, shell, app } from 'electron'
import { existsSync, writeFileSync, readFileSync, rmSync } from 'fs'
import { cp as cpAsync } from 'fs/promises'
import { join } from 'path'
import { spawn } from 'child_process'
import { locatePython, locateBackend, startBackend, waitForBackend } from './backend'

// Mutable so setup:complete can update it after starting the backend.
let currentPort = 0

// Returns the path to a binary inside a venv, platform-aware.
function venvBin(venvPath: string, name: string): string {
    const dir = process.platform === 'win32' ? 'Scripts' : 'bin'
    const ext = process.platform === 'win32' ? '.exe' : ''
    // On Windows, the venv creates 'python.exe' (not 'python3.exe')
    const resolvedName = process.platform === 'win32' && name === 'python3' ? 'python' : name
    return join(venvPath, dir, resolvedName + ext)
}

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
        const backend = locateBackend()

        // Step 0 (packaged Linux/Windows): the bundled Python stores its DLL
        // search path relative to process.resourcesPath (RPATH on Linux,
        // pyvenv.cfg `home` on Windows). After an app update that path is gone,
        // breaking the venv. Fix: copy the entire Python tree to userData once
        // and create the venv from that stable copy.
        let python = locatePython()
        if (app.isPackaged && process.platform !== 'darwin') {
            const stablePythonDir = join(userData, 'python')
            if (!existsSync(stablePythonDir)) {
                const bundledDir = join(process.resourcesPath, 'python')
                event.sender.send('setup:install-deps-progress', {
                    line: 'Extracting Python runtime…', percent: 1,
                })
                await cpAsync(bundledDir, stablePythonDir, { recursive: true })
            }
            python = process.platform === 'win32'
                ? join(stablePythonDir, 'python.exe')
                : join(stablePythonDir, 'bin', 'python3')
        }

        // Step 1: create venv (~5% progress)
        await spawnTracked(python, ['-m', 'venv', venvPath], {}, (line) => {
            event.sender.send('setup:install-deps-progress', { line, percent: 5 })
        })

        // Step 2: pip install requirements (5→95%)
        const pip = venvBin(venvPath, 'pip')
        const requirements = join(backend, 'requirements.txt')
        const installArgs = buildInstallArgs(process.platform, requirements)
        let lineCount = 0
        await spawnTracked(pip, installArgs, {}, (line) => {
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
        const python = venvBin(venvPath, 'python3')
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
        const python = venvBin(venvPath, 'python3')
        const backend = locateBackend()

        const dl = spawnTracked(
            python,
            ['-c', buildDownloadScript(modelId)],
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
                const mBytes = line.match(/^PROGRESS:BYTES:(\d+)$/)
                if (mBytes) {
                    const bytes = parseInt(mBytes[1], 10)
                    console.log(`[progress:${modelId}] ${bytes}B`)
                    event.sender.send('setup:download-model-progress', { modelId, bytes, done: false })
                } else if (line === 'PROGRESS:DONE:0') {
                    event.sender.send('setup:download-model-progress', { modelId, bytes: -1, done: true })
                } else if (line.trim()) {
                    console.log(`[download:${modelId}]`, line)
                }
            }
        )
        activeDownloads.set(modelId, dl)
        try {
            await dl
        } finally {
            activeDownloads.delete(modelId)
        }
    })

    // Cancel all active downloads.
    ipcMain.handle('setup:cancel-download', () => {
        for (const [, dl] of activeDownloads) dl.cancel?.()
        activeDownloads.clear()
    })

    // Read model statuses from the DB (runs during setup, before backend starts).
    ipcMain.handle('setup:get-model-statuses', async () => {
        const userData = app.getPath('userData')
        const venvPath = join(userData, 'venv')
        const python = venvBin(venvPath, 'python3')
        const backend = locateBackend()
        const script = `
import json, sys
sys.path.insert(0, '.')
try:
    from src.db.database import SessionLocal
    from src.db_service import get_all_model_states
    db = SessionLocal()
    try:
        states = get_all_model_states(db)
        # DB uses 'translator', wizard uses 'translation'
        result = {}
        for s in states:
            key = 'translation' if s.name == 'translator' else s.name
            result[key] = s.status
        print(json.dumps(result), flush=True)
    finally:
        db.close()
except Exception:
    print('{}', flush=True)
`
        try {
            const out = await spawnCaptured(python, ['-c', script], {
                cwd: backend,
                env: { ...process.env, APP_DATA_DIR: userData, QUEUE_DB_DIR: userData },
            })
            return JSON.parse(out.trim() || '{}')
        } catch {
            return {}
        }
    })

    // Write marker + env stubs, start the backend, then return so the renderer
    // can switch to app mode knowing the backend is ready.
    ipcMain.handle('setup:complete', async (_, payload?: { skippedModels?: string[]; language?: string }) => {
        const userData = app.getPath('userData')
        writeFileSync(join(userData, 'setup_done'), new Date().toISOString())

        // Persist the language chosen in StepLanguage so apply_bootstrap_settings()
        // can write it to the DB on the very first backend startup. Without this,
        // the backend never learns the non-English language and all translations
        // silently fall back to English.
        const language = payload?.language
        if (language && language !== 'en') {
            writeFileSync(
                join(userData, 'bootstrap.json'),
                JSON.stringify({ default_language: language })
            )
        }

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
        const python = venvBin(venvPath, 'python3')
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
        const python = venvBin(venvPath, 'python3')
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

// Tracks active downloads by modelId so parallel downloads can be cancelled.
const activeDownloads = new Map<string, Promise<void> & { cancel?: () => void }>()

// Builds pip install args. Exported for unit testing.
// PyPI ships CUDA-enabled torch by default on Windows and Linux (~2.5 GB).
// Force CPU-only builds from the PyTorch index to keep the download small.
// macOS uses Metal via the default PyPI wheel so no override is needed.
export function buildInstallArgs(platform: NodeJS.Platform, requirements: string): string[] {
    const args = ['install', '-r', requirements, '--progress-bar', 'off']
    if (platform === 'win32' || platform === 'linux') {
        args.push('--extra-index-url', 'https://download.pytorch.org/whl/cpu')
    }
    return args
}

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
            windowsHide: true,
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
        windowsHide: true,
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

function buildDownloadScript(modelId: string): string {
    return `
import sys, os, traceback
sys.path.insert(0, '.')

# Patch tqdm before any ML import so HuggingFace download progress is captured.
# Uses cumulative bytes across all tqdm instances so multi-file models (e.g.
# translator) don't appear to restart from 0 for each individual file.
from tqdm import tqdm as _Orig

_completed_bytes = 0

class _Reporter(_Orig):
    def __init__(self, *args, **kwargs):
        # Force enabled and redirect tqdm output to devnull.
        # Subclasses like hf_tqdm auto-set disable=True via isatty() when
        # running in a subprocess (no TTY). Forcing disable=False + devnull
        # keeps self.n accurate without polluting stdout.
        kwargs['file'] = open(os.devnull, 'w')
        kwargs['disable'] = False
        super().__init__(*args, **kwargs)

    def update(self, n=1):
        super().update(n)
        if getattr(self, 'unit', None) == 'B' and n:
            total_so_far = _completed_bytes + int(self.n)
            print(f'PROGRESS:BYTES:{total_so_far}', flush=True)

    def close(self):
        global _completed_bytes
        if getattr(self, 'unit', None) == 'B':
            _completed_bytes += int(getattr(self, 'n', 0))
        super().close()

import tqdm as _tm, tqdm.auto as _ta
_tm.tqdm = _ta.tqdm = _Reporter

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

    print('PROGRESS:DONE:0', flush=True)

except Exception:
    print('ERROR: ' + traceback.format_exc(), flush=True)
    sys.exit(1)
`
}
