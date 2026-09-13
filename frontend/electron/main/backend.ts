import { spawn, ChildProcess, execFile } from 'child_process'
import { app } from 'electron'
import path from 'path'
import net from 'net'
import { appendFileSync, closeSync, existsSync, mkdirSync, openSync, readFileSync, unlinkSync, writeFileSync } from 'fs'

let backendProcess: ChildProcess | null = null
let backendStartPromise: Promise<number> | null = null
let backendRuntimeLockFd: number | null = null
let _port: number | null = null

// Log file written to userData so users can share it when reporting issues.
let _logPath: string | null = null
export function logToFile(line: string): void {
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

const DEFAULT_BACKEND_READY_RETRIES = 60
const WINDOWS_PACKAGED_BACKEND_READY_RETRIES = 360

// Returns the venv Python created during setup (has all pip packages installed).
// On Windows packaged builds we use python.exe with windowsHide=true so stderr
// and stdout are captured in photorag.log while still avoiding a console window.
export function locateVenvPython(forServer = false): string {
    const venvBase = path.join(app.getPath('userData'), 'venv')
    if (process.platform === 'win32') {
        if (forServer && !app.isPackaged) {
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

export function getSetupDonePath(): string {
    return path.join(app.getPath('userData'), 'setup_done')
}

function readWindowsPeMachine(exePath: string): number | null {
    try {
        const buf = readFileSync(exePath)
        if (buf.length < 0x40 || buf.toString('ascii', 0, 2) !== 'MZ') return null

        const peOffset = buf.readUInt32LE(0x3c)
        if (buf.length < peOffset + 6) return null
        if (buf.toString('ascii', peOffset, peOffset + 4) !== 'PE\0\0') return null

        return buf.readUInt16LE(peOffset + 4)
    } catch {
        return null
    }
}

export function isCompatibleWindowsExecutable(exePath: string): boolean {
    if (process.platform !== 'win32') return true

    const machine = readWindowsPeMachine(exePath)
    if (machine === null) return false

    if (process.arch === 'x64') return machine === 0x8664
    if (process.arch === 'arm64') return machine === 0xaa64
    if (process.arch === 'ia32') return machine === 0x014c
    return true
}

export function getBackendSetupIssue(): string | null {
    if (!existsSync(getSetupDonePath())) {
        return 'setup marker is missing'
    }

    const python = locateVenvPython(true)
    if (!existsSync(python)) {
        return `venv Python is missing: ${python}`
    }

    if (!isCompatibleWindowsExecutable(python)) {
        return `venv Python is not a compatible Windows executable: ${python}`
    }

    const runPy = path.join(locateBackend(), 'run.py')
    if (!existsSync(runPy)) {
        return `backend entrypoint is missing: ${runPy}`
    }

    return null
}

function getAppDataDir(): string {
    return app.getPath('userData')
}

function windowsBackendRuntimeLockEnabled(): boolean {
    return process.platform === 'win32' && app.isPackaged
}

function getBackendRuntimeLockPath(): string {
    return path.join(getAppDataDir(), 'backend_runtime.lock')
}

function getBackendRuntimePortPath(): string {
    return path.join(getAppDataDir(), 'backend_runtime_port')
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

export function backendReadyRetries(): number {
    return app.isPackaged && process.platform === 'win32'
        ? WINDOWS_PACKAGED_BACKEND_READY_RETRIES
        : DEFAULT_BACKEND_READY_RETRIES
}

function logWindowsDebugCommand(python: string, backendDir: string, port: number, appDataDir: string): void {
    if (process.platform !== 'win32') return

    const hfCache = path.join(appDataDir, '.hf_cache')
    logToFile([
        '[startup] Windows backend debug command (cmd.exe):',
        `cd /d "${backendDir}"`,
        `set "APP_DATA_DIR=${appDataDir}"`,
        `set "API_PORT=${port}"`,
        `set "QUEUE_DB_DIR=${appDataDir}"`,
        `set "HUGGINGFACE_HUB_CACHE=${hfCache}"`,
        `"${python}" run.py`,
    ].join('\n'))
}

function quotePowerShellString(value: string): string {
    return `'${value.replace(/'/g, "''")}'`
}

export function cleanupStaleWindowsBackendProcesses(reason = 'startup'): Promise<void> {
    if (process.platform !== 'win32' || !app.isPackaged) {
        return Promise.resolve()
    }

    const venvPython = locateVenvPython(true)
    const script = [
        `$venvPython = ${quotePowerShellString(venvPython)}`,
        '$matches = Get-CimInstance Win32_Process | Where-Object {',
        '    $_.ProcessId -ne $PID -and',
        '    $_.CommandLine -and',
        '    $_.CommandLine.Contains($venvPython) -and',
        "    ($_.CommandLine.Contains(' run.py') -or $_.CommandLine.Contains('huey.bin.huey_consumer'))",
        '}',
        'foreach ($proc in $matches) {',
        '    try {',
        '        Stop-Process -Id $proc.ProcessId -Force -ErrorAction Stop',
        '        Write-Output "[cleanup] stopped PID $($proc.ProcessId): $($proc.CommandLine)"',
        '    } catch {',
        '        Write-Output "[cleanup] failed PID $($proc.ProcessId): $($_.Exception.Message)"',
        '    }',
        '}',
    ].join('\n')

    logToFile(`[cleanup] checking stale Windows backend processes before ${reason}`)

    return new Promise((resolve) => {
        execFile(
            'powershell.exe',
            ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', script],
            { windowsHide: true },
            (error, stdout, stderr) => {
                const out = `${stdout ?? ''}${stderr ?? ''}`.trim()
                if (out) logToFile(out)
                if (error) logToFile(`[cleanup] stale process cleanup failed: ${error.message}`)
                resolve()
            }
        )
    })
}

function writeBackendRuntimePort(port: number): void {
    if (!windowsBackendRuntimeLockEnabled()) return
    try {
        writeFileSync(getBackendRuntimePortPath(), String(port))
    } catch (error) {
        logToFile(`[startup] failed to write backend runtime port: ${error instanceof Error ? error.message : String(error)}`)
    }
}

function readBackendRuntimePort(): number | null {
    try {
        const raw = readFileSync(getBackendRuntimePortPath(), 'utf8').trim()
        const port = Number(raw)
        return Number.isInteger(port) && port > 0 ? port : null
    } catch {
        return null
    }
}

async function waitForExistingWindowsBackend(): Promise<number | null> {
    if (!windowsBackendRuntimeLockEnabled()) return null

    for (let i = 0; i < 60; i++) {
        const port = readBackendRuntimePort()
        if (port !== null) {
            try {
                await waitForBackend(port, 2)
                logToFile(`[startup] reusing backend runtime from lock on port ${port}`)
                return port
            } catch {
                // Keep waiting briefly: another Electron process may still be starting it.
            }
        }
        await new Promise(resolve => setTimeout(resolve, 500))
    }

    return null
}

async function acquireWindowsBackendRuntimeLock(): Promise<'owned' | { reusePort: number }> {
    if (!windowsBackendRuntimeLockEnabled()) return 'owned'

    const lockPath = getBackendRuntimeLockPath()
    try {
        backendRuntimeLockFd = openSync(lockPath, 'wx')
        writeFileSync(backendRuntimeLockFd, `${process.pid}\n${new Date().toISOString()}\n`)
        logToFile(`[startup] acquired backend runtime lock: ${lockPath}`)
        return 'owned'
    } catch (error) {
        const code = error && typeof error === 'object' && 'code' in error
            ? String((error as { code?: unknown }).code)
            : ''
        if (code !== 'EEXIST') throw error

        logToFile(`[startup] backend runtime lock already exists: ${lockPath}`)
        const existingPort = await waitForExistingWindowsBackend()
        if (existingPort !== null) return { reusePort: existingPort }

        logToFile('[startup] backend runtime lock appears stale; cleaning stale backend processes')
        await cleanupStaleWindowsBackendProcesses('stale backend runtime lock recovery')
        removeStaleWindowsBackendRuntimeLock()

        backendRuntimeLockFd = openSync(lockPath, 'w')
        writeFileSync(backendRuntimeLockFd, `${process.pid}\n${new Date().toISOString()}\n`)
        logToFile(`[startup] replaced stale backend runtime lock: ${lockPath}`)
        return 'owned'
    }
}

function releaseWindowsBackendRuntimeLock(): void {
    if (!windowsBackendRuntimeLockEnabled()) return

    if (backendRuntimeLockFd === null) return
    try { closeSync(backendRuntimeLockFd) } catch { /* ignore cleanup errors */ }
    backendRuntimeLockFd = null
    try { unlinkSync(getBackendRuntimeLockPath()) } catch { /* ignore cleanup errors */ }
    try { unlinkSync(getBackendRuntimePortPath()) } catch { /* ignore cleanup errors */ }
}

function removeStaleWindowsBackendRuntimeLock(): void {
    if (!windowsBackendRuntimeLockEnabled()) return
    try { unlinkSync(getBackendRuntimeLockPath()) } catch { /* ignore cleanup errors */ }
    try { unlinkSync(getBackendRuntimePortPath()) } catch { /* ignore cleanup errors */ }
}

export async function startBackend(): Promise<number> {
    if (backendStartPromise) {
        logToFile('[startup] backend startup already in progress; joining existing operation')
        return backendStartPromise
    }

    if (backendProcess && _port !== null) {
        logToFile(`[startup] backend already running on port ${_port}; reusing existing process`)
        return _port
    }

    backendStartPromise = startBackendProcess()
    try {
        return await backendStartPromise
    } finally {
        backendStartPromise = null
    }
}

async function startBackendProcess(): Promise<number> {
    const runtimeLock = await acquireWindowsBackendRuntimeLock()
    if (runtimeLock !== 'owned') {
        _port = runtimeLock.reusePort
        return runtimeLock.reusePort
    }

    await cleanupStaleWindowsBackendProcesses('backend startup')

    const port = await findFreePort()
    const appDataDir = getAppDataDir()
    // Packaged Windows uses python.exe + windowsHide so logs are captured.
    const python = app.isPackaged ? locateVenvPython(true) : 'python3'
    const backendDir = locateBackend()
    const backendEnv: NodeJS.ProcessEnv = {
        ...process.env,
        APP_DATA_DIR: appDataDir,
        API_PORT: String(port),
        QUEUE_DB_DIR: appDataDir,
        HUGGINGFACE_HUB_CACHE: path.join(appDataDir, '.hf_cache'),
    }

    logToFile(`[startup] python=${python} args=run.py backendDir=${backendDir} port=${port}`)
    logWindowsDebugCommand(python, backendDir, port, appDataDir)

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
        env: backendEnv,
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
        releaseWindowsBackendRuntimeLock()
    })

    _port = port
    writeBackendRuntimePort(port)

    // Wait here so the caller gets a rich error if startup fails.
    try {
        await waitForBackend(port, backendReadyRetries())
    } catch {
        const tail = startupLines.slice(-30).join('\n') || '(no output captured)'
        const logHint = _logPath ? `\n\nFull log: ${_logPath}` : ''
        stopBackend()
        throw new Error(
            `Backend did not respond on port ${port}.\n\n` +
            `Last output:\n${tail}${logHint}`
        )
    }

    return port
}

export function stopBackend(): void {
    backendStartPromise = null
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
    releaseWindowsBackendRuntimeLock()
    void cleanupStaleWindowsBackendProcesses('app shutdown')
    _port = null
}

export function getBackendPort(): number | null {
    return _port
}
