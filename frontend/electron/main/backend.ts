import { spawn, ChildProcess } from 'child_process'
import { app } from 'electron'
import path from 'path'
import net from 'net'

let backendProcess: ChildProcess | null = null
let _port: number | null = null

export function locatePython(): string {
    if (app.isPackaged) {
        const bin = process.platform === 'win32'
            ? 'python.exe'
            : path.join('bin', 'python3')
        return path.join(process.resourcesPath, 'python', bin)
    }
    return process.platform === 'win32' ? 'python' : 'python3'
}

// Returns the venv Python created during setup (has all pip packages installed).
export function locateVenvPython(): string {
    const rel = process.platform === 'win32'
        ? path.join('Scripts', 'python.exe')
        : path.join('bin', 'python3')
    return path.join(app.getPath('userData'), 'venv', rel)
}

export function locateBackend(): string {
    if (app.isPackaged) {
        return path.join(process.resourcesPath, 'backend')
    }
    // In dev: electron/main/__dirname → out/main → project root is 3 levels up from src
    return path.join(__dirname, '../../../backend')
}

function getAppDataDir(): string {
    return app.getPath('userData')
}

export async function findFreePort(start = 8000): Promise<number> {
    return new Promise((resolve, reject) => {
        const server = net.createServer()
        server.listen(start, () => {
            const addr = server.address()
            const port = typeof addr === 'object' && addr ? addr.port : start
            server.close(() => resolve(port))
        })
        server.on('error', () => {
            findFreePort(start + 1).then(resolve).catch(reject)
        })
    })
}

export async function waitForBackend(port: number, maxRetries = 60): Promise<void> {
    for (let i = 0; i < maxRetries; i++) {
        try {
            const res = await fetch(`http://127.0.0.1:${port}/api/system/status/`)
            if (res.ok) return
        } catch {
            // not ready yet
        }
        await new Promise(r => setTimeout(r, 500))
    }
    throw new Error(`Backend did not start on port ${port} after ${maxRetries} retries`)
}

export async function startBackend(): Promise<number> {
    const port = await findFreePort()
    const appDataDir = getAppDataDir()
    // Packaged: use venv Python (has all pip packages). Dev: use system python3.
    const python = app.isPackaged ? locateVenvPython() : 'python3'
    const backendDir = locateBackend()

    backendProcess = spawn(python, ['run.py'], {
        cwd: backendDir,
        detached: true,
        windowsHide: true,
        env: {
            ...process.env,
            APP_DATA_DIR: appDataDir,
            API_PORT: String(port),
            QUEUE_DB_DIR: appDataDir,
            HUGGINGFACE_HUB_CACHE: path.join(appDataDir, '.hf_cache'),
        },
    })

    backendProcess.stdout?.on('data', (d: Buffer) =>
        console.log('[backend]', d.toString().trimEnd()))
    backendProcess.stderr?.on('data', (d: Buffer) =>
        console.error('[backend]', d.toString().trimEnd()))
    backendProcess.on('exit', (code: number | null) => {
        console.log(`[backend] exited with code ${code}`)
        backendProcess = null
        _port = null
    })

    _port = port
    return port
}

export function stopBackend(): void {
    if (backendProcess?.pid) {
        const pid = backendProcess.pid
        if (process.platform === 'win32') {
            // Kill the entire process tree (/T) forcefully (/F)
            spawn('taskkill', ['/F', '/T', '/PID', String(pid)], { windowsHide: true })
        } else {
            try { process.kill(-pid, 'SIGTERM') } catch { /* already gone */ }
            setTimeout(() => {
                try { process.kill(-pid, 'SIGKILL') } catch { /* already gone */ }
            }, 5000)
        }
        backendProcess = null
    }
    _port = null
}

export function getBackendPort(): number | null {
    return _port
}
