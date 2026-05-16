import { spawn, ChildProcess } from 'child_process'
import { app } from 'electron'
import path from 'path'
import net from 'net'

let backendProcess: ChildProcess | null = null
let _port: number | null = null

export function locatePython(): string {
    if (app.isPackaged) {
        return path.join(process.resourcesPath, 'python', 'bin', 'python3')
    }
    return 'python3'
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
    const python = locatePython()
    const backendDir = locateBackend()

    backendProcess = spawn(python, ['run.py'], {
        cwd: backendDir,
        detached: true,
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
        try {
            process.kill(-backendProcess.pid, 'SIGTERM')
            const pid = backendProcess.pid
            setTimeout(() => {
                try { process.kill(-pid, 'SIGKILL') } catch { /* already gone */ }
            }, 5000)
        } catch { /* already gone */ }
        backendProcess = null
    }
    _port = null
}

export function getBackendPort(): number | null {
    return _port
}
