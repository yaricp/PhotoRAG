import { spawn, ChildProcess } from 'child_process'
import { app } from 'electron'
import path from 'path'
import net from 'net'
import { existsSync, appendFileSync, mkdirSync } from 'fs'

let backendProcess: ChildProcess | null = null
let _port: number | null = null

// Log file written to userData so users can share it when reporting issues.
let _logPath: string | null = null
function logToFile(line: string): void {
    try {
        if (!_logPath) {
            const dir = app.getPath('userData')
            mkdirSync(dir, { recursive: true })
            _logPath = path.join(dir, 'photorag.log')
        }
        appendFileSync(_logPath, `${new Date().toISOString()} ${line}\n`)
    } catch { /* ignore log errors */ }
}

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
// forServer=true prefers pythonw.exe on Windows (windowless, no console window).
// Falls back to python.exe if pythonw.exe was not bundled in this venv.
export function locateVenvPython(forServer = false): string {
    const venvBase = path.join(app.getPath('userData'), 'venv')
    if (process.platform === 'win32') {
        if (forServer) {
            const pythonw = path.join(venvBase, 'Scripts', 'pythonw.exe')
            if (existsSync(pythonw)) return pythonw
            // pythonw.exe not present — fall back to python.exe (windowsHide suppresses the window)
        }
        return path.join(venvBase, 'Scripts', 'python.exe')
    }
    return path.join(venvBase, 'bin', 'python3')
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
    // Packaged: prefer pythonw.exe (windowless) for the server; falls back to python.exe.
    const python = app.isPackaged ? locateVenvPython(true) : 'python3'
    const backendDir = locateBackend()

    logToFile(`[startup] python=${python} backendDir=${backendDir} port=${port}`)

    // Collect startup output so we can include it in the error dialog if the
    // backend fails to come up.
    const startupLines: string[] = []

    backendProcess = spawn(python, ['run.py'], {
        cwd: backendDir,
        // detached on macOS/Linux lets the backend survive a renderer crash.
        // On Windows, detached always allocates a new console window even with
        // windowsHide, so we skip it there.
        detached: process.platform !== 'win32',
        windowsHide: true,
        env: {
            ...process.env,
            APP_DATA_DIR: appDataDir,
            API_PORT: String(port),
            QUEUE_DB_DIR: appDataDir,
            HUGGINGFACE_HUB_CACHE: path.join(appDataDir, '.hf_cache'),
        },
    })

    backendProcess.on('error', (err) => {
        const msg = `[backend spawn error] ${err.message}`
        console.error(msg)
        logToFile(msg)
        startupLines.push(msg)
    })

    backendProcess.stdout?.on('data', (d: Buffer) => {
        const text = d.toString().trimEnd()
        console.log('[backend]', text)
        logToFile(`[backend:out] ${text}`)
        startupLines.push(text)
    })
    backendProcess.stderr?.on('data', (d: Buffer) => {
        const text = d.toString().trimEnd()
        console.error('[backend]', text)
        logToFile(`[backend:err] ${text}`)
        startupLines.push(text)
    })
    backendProcess.on('exit', (code: number | null) => {
        const msg = `[backend] exited with code ${code}`
        console.log(msg)
        logToFile(msg)
        backendProcess = null
        _port = null
    })

    _port = port

    // Wait here so the caller gets a rich error if startup fails.
    try {
        await waitForBackend(port)
    } catch {
        const tail = startupLines.slice(-30).join('\n') || '(no output captured)'
        const logHint = _logPath ? `\n\nFull log: ${_logPath}` : ''
        throw new Error(
            `Backend did not respond on port ${port}.\n\n` +
            `Last output:\n${tail}${logHint}`
        )
    }

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
