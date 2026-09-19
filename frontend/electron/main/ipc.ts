import { ipcMain, dialog, shell, app } from 'electron'
import { closeSync, existsSync, openSync, readFileSync, rmSync, unlinkSync, writeFileSync } from 'fs'
import { cp as cpAsync } from 'fs/promises'
import { join } from 'path'
import { spawn } from 'child_process'
import { locatePython, locateBackend, startBackend, logToFile, getBackendSetupIssue } from './backend'

// Mutable so setup:complete can update it after starting the backend.
let currentPort = 0
let installDepsPromise: Promise<void> | null = null
const SETUP_LOCK_POLL_MS = 1000
const SETUP_LOCK_MAX_POLLS = 60 * 60

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
        return { needed: getBackendSetupIssue() !== null }
    })

    // Install Python deps into userData/venv and stream progress back.
    ipcMain.handle('setup:install-deps', async (event) => {
        if (installDepsPromise) {
            logToFile('[setup] dependency installation already running; joining existing operation')
            return installDepsPromise
        }

        installDepsPromise = (async () => {
            const lock = await acquireSetupInstallLock()
            if (lock === null) return

            try {
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
                    const bundledDir = join(process.resourcesPath, 'python')
                    logToFile(`[setup] refreshing Python runtime from ${bundledDir} to ${stablePythonDir}`)
                    event.sender.send('setup:install-deps-progress', {
                        line: 'Extracting Python runtime…', percent: 1,
                    })
                    rmSync(stablePythonDir, { recursive: true, force: true })
                    await cpAsync(bundledDir, stablePythonDir, { recursive: true })
                    python = process.platform === 'win32'
                        ? join(stablePythonDir, 'python.exe')
                        : join(stablePythonDir, 'bin', 'python3')
                }

                // Step 1: create venv (~5% progress)
                logToFile(`[setup] recreating venv at ${venvPath}`)
                rmSync(venvPath, { recursive: true, force: true })
                await spawnTracked(python, ['-m', 'venv', venvPath], {}, (line) => {
                    logToFile(`[setup:venv] ${line}`)
                    event.sender.send('setup:install-deps-progress', { line, percent: 5 })
                })

                // Step 2: pip install requirements (5→95%)
                const venvPython = venvBin(venvPath, 'python3')
                const requirements = join(backend, 'requirements.txt')
                const installArgs = ['-m', 'pip', ...buildInstallArgs(process.platform, requirements)]
                let lineCount = 0
                logToFile(`[setup] installing requirements: ${quoteCommand([venvPython, ...installArgs])}`)
                await spawnTracked(venvPython, installArgs, { env: buildSetupProcessEnv() }, (line) => {
                    logToFile(`[setup:pip] ${line}`)
                    lineCount++
                    const percent = Math.min(95, 5 + lineCount * 0.5)
                    event.sender.send('setup:install-deps-progress', { line, percent })
                })

                logToFile('[setup] Python dependencies installed')
                event.sender.send('setup:install-deps-progress', { line: 'Done.', percent: 100 })
            } finally {
                releaseSetupInstallLock(lock)
            }
        })()

        try {
            return await installDepsPromise
        } finally {
            installDepsPromise = null
        }
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
        const downloadLines: string[] = []

        logToFile(`[setup:download:${modelId}] starting model download`)

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
                    logToFile(`[setup:download:${modelId}] done`)
                    event.sender.send('setup:download-model-progress', { modelId, bytes: -1, done: true })
                } else if (line.trim()) {
                    downloadLines.push(line)
                    if (downloadLines.length > 40) downloadLines.shift()
                    logToFile(`[setup:download:${modelId}] ${line}`)
                    console.log(`[download:${modelId}]`, line)
                }
            }
        )
        activeDownloads.set(modelId, dl)
        try {
            await dl
        } catch (error) {
            const tail = downloadLines.slice(-20).join('\n') || '(no model download output captured)'
            const wrapped = new Error(
                `Model download failed for ${modelId}: ${error instanceof Error ? error.message : String(error)}\n\n` +
                `Last output:\n${tail}`
            )
            ;(wrapped as Error & { cause?: unknown }).cause = error
            throw wrapped
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
        if (skipped.has('clip'))        envLines.push('CLIP_MODE=remote')
        if (skipped.has('embedding'))   envLines.push('EMBEDDING_MODE=remote')
        if (skipped.has('translation')) envLines.push('TRANSLATOR_MODE=remote')
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
    ipcMain.handle('setup:save-model-configs', async (_, configs: Array<Record<string, unknown>>) => {
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
            stdio: ['ignore', 'pipe', 'pipe'],
        })
        let stdout = ''
        let stderr = ''
        let settled = false
        const finish = (code: number | null) => {
            if (settled) return
            settled = true
            if (code === 0) resolve(stdout)
            else reject(new Error(`Process exited with code ${code}: ${stderr || stdout}`))
        }
        child.stdout?.on('data', (d: Buffer) => { stdout += d.toString() })
        child.stderr?.on('data', (d: Buffer) => { stderr += d.toString() })
        child.on('exit', finish)
        child.on('close', finish)
        child.on('error', (e) => {
            if (settled) return
            settled = true
            reject(e)
        })
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
        stdio: ['ignore', 'pipe', 'pipe'],
    })

    let buf = ''
    let settled = false
    const handleData = (data: Buffer) => {
        buf += data.toString()
        const lines = buf.split('\n')
        buf = lines.pop() ?? ''
        lines.forEach(line => onLine?.(line))
    }
    child.stdout?.on('data', handleData)
    child.stderr?.on('data', handleData)

    const finish = (code: number | null) => {
        if (settled) return
        settled = true
        if (buf) onLine?.(buf)
        if (code === 0) resolveFn!()
        else rejectFn!(new Error(`Process exited with code ${code}`))
    }
    child.on('exit', finish)
    child.on('close', finish)
    child.on('error', (e) => {
        if (settled) return
        settled = true
        rejectFn!(e)
    })

    const cancellable = promise as Promise<void> & { cancel?: () => void }
    cancellable.cancel = () => { child.kill('SIGTERM') }
    return cancellable
}

function buildSetupProcessEnv(): NodeJS.ProcessEnv {
    return {
        ...process.env,
        PIP_NO_INPUT: '1',
        PYTHONUNBUFFERED: '1',
        PYTHONIOENCODING: 'utf-8',
    }
}

function getSetupInstallLockPath(): string {
    return join(app.getPath('userData'), 'setup_install_deps.lock')
}

async function acquireSetupInstallLock(): Promise<number | null> {
    const lockPath = getSetupInstallLockPath()
    try {
        const fd = openSync(lockPath, 'wx')
        writeFileSync(fd, `${process.pid}\n${new Date().toISOString()}\n`)
        logToFile(`[setup] acquired dependency installation lock: ${lockPath}`)
        return fd
    } catch (error) {
        const code = error && typeof error === 'object' && 'code' in error
            ? String((error as { code?: unknown }).code)
            : ''
        if (code !== 'EEXIST') throw error
        logToFile(`[setup] dependency installation lock already exists; waiting: ${lockPath}`)
        await waitForSetupInstallLockRelease(lockPath)
        return null
    }
}

function releaseSetupInstallLock(fd: number): void {
    const lockPath = getSetupInstallLockPath()
    try { closeSync(fd) } catch { /* ignore lock cleanup errors */ }
    try {
        unlinkSync(lockPath)
        logToFile(`[setup] released dependency installation lock: ${lockPath}`)
    } catch { /* ignore lock cleanup errors */ }
}

async function waitForSetupInstallLockRelease(lockPath: string): Promise<void> {
    for (let i = 0; i < SETUP_LOCK_MAX_POLLS; i++) {
        if (!existsSync(lockPath)) return
        await new Promise(resolve => setTimeout(resolve, SETUP_LOCK_POLL_MS))
    }
    throw new Error(`Dependency installation is already running and did not finish: ${lockPath}`)
}

function quoteCommand(parts: string[]): string {
    return parts
        .map((part) => /\s/.test(part) ? `"${part.replace(/"/g, '\\"')}"` : part)
        .join(' ')
}

export function buildDownloadScript(modelId: string): string {
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

    VC_REDIST_URL = 'https://aka.ms/vs/17/release/vc_redist.x64.exe'
    TORCH_BACKED_MODELS = {'clip', 'embedding', 'vision', 'translation', 'ocr', 'chat'}

    def check_windows_torch_runtime(model_id):
        if os.name != 'nt' or model_id not in TORCH_BACKED_MODELS:
            return
        try:
            import torch  # noqa: F401
        except OSError as exc:
            message = str(exc)
            winerror = getattr(exc, 'winerror', None)
            if winerror == 126 or 'c10.dll' in message or 'Microsoft Visual C++ Redistributable' in message:
                print('ERROR: Microsoft Visual C++ Redistributable x64 is required for local AI models on Windows.', flush=True)
                print(f'ERROR: Install it from {VC_REDIST_URL}, restart PhotoRAG, then retry model setup.', flush=True)
            raise

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

    check_windows_torch_runtime(model_id)

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
