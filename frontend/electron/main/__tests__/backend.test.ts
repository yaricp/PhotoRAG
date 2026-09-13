import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// Shared mock state — recreated fresh for each test via beforeEach
let mockSpawnProcess = {
    pid: 42000,
    stdout: { on: vi.fn() },
    stderr: { on: vi.fn() },
    on: vi.fn(),
    kill: vi.fn(),
}

let isPackaged = false
let appendFileSyncMock = vi.fn()
let existsSyncMock = vi.fn(() => false)
let readFileSyncMock = vi.fn()
let openSyncMock = vi.fn(() => 43)
let closeSyncMock = vi.fn()
let unlinkSyncMock = vi.fn()
let writeFileSyncMock = vi.fn()
let execFileMock = vi.fn()
const userData = '/Users/test/Library/Application Support/PhotoRAG'

function windowsPe(machine: number): Buffer {
    const buf = Buffer.alloc(128)
    buf.write('MZ', 0, 'ascii')
    buf.writeUInt32LE(0x40, 0x3c)
    buf.write('PE\0\0', 0x40, 'ascii')
    buf.writeUInt16LE(machine, 0x44)
    return buf
}

beforeEach(() => {
    isPackaged = false
    mockSpawnProcess = {
        pid: 42000,
        stdout: { on: vi.fn() },
        stderr: { on: vi.fn() },
        on: vi.fn(),
        kill: vi.fn(),
    }

    // Reset module registry so each test imports a fresh backend.ts
    vi.resetModules()
    appendFileSyncMock = vi.fn()
    existsSyncMock = vi.fn(() => false)
    readFileSyncMock = vi.fn()
    openSyncMock = vi.fn(() => 43)
    closeSyncMock = vi.fn()
    unlinkSyncMock = vi.fn()
    writeFileSyncMock = vi.fn()
    execFileMock = vi.fn((_cmd, _args, _opts, cb) => cb(null, '', ''))

    // Register mocks for fresh imports to pick up.
    // Node built-in mocks need a `default` export for Vitest's ESM interop.
    const spawnMock = vi.fn(() => mockSpawnProcess)
    vi.doMock('child_process', () => ({
        default: { spawn: spawnMock, execFile: execFileMock },
        spawn: spawnMock,
        execFile: execFileMock,
    }))

    const appMock = {
        get isPackaged() { return isPackaged },
        getPath: vi.fn(() => userData),
    }
    vi.doMock('electron', () => ({
        default: { app: appMock },
        app: appMock,
    }))

    const mockServer = {
        listen: vi.fn((_port: number, cb: () => void) => cb()),
        close: vi.fn((cb: () => void) => cb()),
        address: vi.fn(() => ({ port: 9100 })),
        on: vi.fn(),
    }
    const createServerMock = vi.fn(() => mockServer)
    vi.doMock('net', () => ({
        default: { createServer: createServerMock },
        createServer: createServerMock,
    }))

    // startBackend now calls waitForBackend internally; mock fetch so tests don't hang.
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }))

    vi.doMock('fs', () => ({
        default: {
            existsSync: existsSyncMock,
            appendFileSync: appendFileSyncMock,
            closeSync: closeSyncMock,
            mkdirSync: vi.fn(),
            openSync: openSyncMock,
            readFileSync: readFileSyncMock,
            unlinkSync: unlinkSyncMock,
            writeFileSync: writeFileSyncMock,
        },
        existsSync: existsSyncMock,
        appendFileSync: appendFileSyncMock,
        closeSync: closeSyncMock,
        mkdirSync: vi.fn(),
        openSync: openSyncMock,
        readFileSync: readFileSyncMock,
        unlinkSync: unlinkSyncMock,
        writeFileSync: writeFileSyncMock,
    }))
})

afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
})

// -----------------------------------------------------------------------
// findFreePort
// -----------------------------------------------------------------------
describe('findFreePort', () => {
    it('returns a number', async () => {
        const { findFreePort } = await import('../backend')
        const port = await findFreePort(9100)
        expect(typeof port).toBe('number')
        expect(port).toBeGreaterThan(0)
    })

    it('returns the mocked port value', async () => {
        const { findFreePort } = await import('../backend')
        const port = await findFreePort(9100)
        expect(port).toBe(9100)
    })
})

// -----------------------------------------------------------------------
// setup readiness
// -----------------------------------------------------------------------
describe('getBackendSetupIssue', () => {
    it('requires setup when the setup marker is missing', async () => {
        isPackaged = true
        const { getBackendSetupIssue } = await import('../backend')
        expect(getBackendSetupIssue()).toBe('setup marker is missing')
    })

    it('requires setup when the venv Python is missing', async () => {
        isPackaged = true
        existsSyncMock.mockImplementation((file: string) => file.endsWith('setup_done'))
        const { getBackendSetupIssue } = await import('../backend')
        expect(getBackendSetupIssue()).toContain('venv Python is missing')
    })

    it('requires setup when packaged Windows venv Python is the wrong PE architecture', async () => {
        isPackaged = true
        vi.stubGlobal('process', { ...process, platform: 'win32', arch: 'x64', resourcesPath: 'C:\\mock\\resources' })
        existsSyncMock.mockReturnValue(true)
        readFileSyncMock.mockReturnValue(windowsPe(0xaa64))
        const { getBackendSetupIssue } = await import('../backend')
        expect(getBackendSetupIssue()).toContain('not a compatible Windows executable')
    })

    it('accepts packaged Windows setup when venv Python matches the Electron architecture', async () => {
        isPackaged = true
        vi.stubGlobal('process', { ...process, platform: 'win32', arch: 'x64', resourcesPath: 'C:\\mock\\resources' })
        existsSyncMock.mockReturnValue(true)
        readFileSyncMock.mockReturnValue(windowsPe(0x8664))
        const { getBackendSetupIssue } = await import('../backend')
        expect(getBackendSetupIssue()).toBeNull()
    })
})

// -----------------------------------------------------------------------
// startBackend
// -----------------------------------------------------------------------
describe('startBackend', () => {
    it('uses python3 in dev mode', async () => {
        isPackaged = false
        const { startBackend } = await import('../backend')
        const cp = await import('child_process')
        await startBackend()
        expect(cp.spawn).toHaveBeenCalledWith('python3', expect.any(Array), expect.any(Object))
    })

    it('uses venv python path when packaged', async () => {
        isPackaged = true
        vi.stubGlobal('process', { ...process, resourcesPath: '/mock/resources' })
        const { startBackend } = await import('../backend')
        const cp = await import('child_process')
        await startBackend()
        const pythonArg = (cp.spawn as ReturnType<typeof vi.fn>).mock.calls[0][0] as string
        expect(pythonArg).toContain('python3')
        // After setup, the venv Python is used (not the bundled Python in Resources)
        expect(pythonArg).toContain('venv')
        expect(pythonArg).toContain(userData)
    })

    it('uses python.exe for packaged Windows so backend output is captured', async () => {
        isPackaged = true
        vi.stubGlobal('process', { ...process, platform: 'win32', resourcesPath: 'C:\\mock\\resources' })
        const { startBackend } = await import('../backend')
        const cp = await import('child_process')
        await startBackend()
        const pythonArg = (cp.spawn as ReturnType<typeof vi.fn>).mock.calls[0][0] as string
        expect(pythonArg).toContain('python.exe')
        expect(pythonArg).not.toContain('pythonw.exe')
    })

    it('does not detach the packaged Windows backend process', async () => {
        isPackaged = true
        vi.stubGlobal('process', { ...process, platform: 'win32', resourcesPath: 'C:\\mock\\resources' })
        const { startBackend } = await import('../backend')
        const cp = await import('child_process')
        await startBackend()
        const opts = (cp.spawn as ReturnType<typeof vi.fn>).mock.calls[0][2] as { detached: boolean; windowsHide: boolean }
        expect(opts.detached).toBe(false)
        expect(opts.windowsHide).toBe(true)
    })

    it('logs a copy-pasteable Windows backend debug command', async () => {
        isPackaged = true
        vi.stubGlobal('process', { ...process, platform: 'win32', resourcesPath: 'C:\\mock\\resources' })
        const { startBackend } = await import('../backend')
        await startBackend()
        const written = appendFileSyncMock.mock.calls
            .map((call) => String(call[1]))
            .join('\n')
        expect(written).toContain('Windows backend debug command (cmd.exe)')
        expect(written).toContain('cd /d')
        expect(written).toContain('set "APP_DATA_DIR=')
        expect(written).toContain('set "API_PORT=9100"')
        expect(written).toContain('set "QUEUE_DB_DIR=')
        expect(written).toContain('set "HUGGINGFACE_HUB_CACHE=')
        expect(written).toContain('" run.py')
    })

    it('uses a longer readiness wait budget for packaged Windows', async () => {
        isPackaged = true
        vi.stubGlobal('process', { ...process, platform: 'win32', resourcesPath: 'C:\\mock\\resources' })
        const { backendReadyRetries } = await import('../backend')
        expect(backendReadyRetries()).toBe(360)
    })

    it('cleans stale packaged Windows backend processes before starting', async () => {
        isPackaged = true
        vi.stubGlobal('process', { ...process, platform: 'win32', resourcesPath: 'C:\\mock\\resources' })
        const { startBackend } = await import('../backend')
        await startBackend()
        expect(execFileMock).toHaveBeenCalledWith(
            'powershell.exe',
            expect.arrayContaining(['-Command', expect.stringContaining('huey.bin.huey_consumer')]),
            expect.objectContaining({ windowsHide: true }),
            expect.any(Function)
        )
        const script = execFileMock.mock.calls[0][1][4] as string
        expect(script).toContain('run.py')
        expect(script).toContain('venv')
        expect(script).toContain('Scripts')
        expect(script).toContain('python.exe')
        expect(script).not.toContain('pip.exe')
    })

    it('skips stale backend cleanup outside packaged Windows', async () => {
        isPackaged = false
        const { startBackend } = await import('../backend')
        await startBackend()
        expect(execFileMock).not.toHaveBeenCalled()
    })

    it('passes APP_DATA_DIR env var pointing to userData', async () => {
        const { startBackend } = await import('../backend')
        const cp = await import('child_process')
        await startBackend()
        const opts = (cp.spawn as ReturnType<typeof vi.fn>).mock.calls[0][2] as { env: Record<string, string> }
        expect(opts.env.APP_DATA_DIR).toBe(userData)
    })

    it('passes API_PORT env var matching the returned port', async () => {
        const { startBackend } = await import('../backend')
        const cp = await import('child_process')
        const port = await startBackend()
        const opts = (cp.spawn as ReturnType<typeof vi.fn>).mock.calls[0][2] as { env: Record<string, string> }
        expect(opts.env.API_PORT).toBe(String(port))
    })

    it('passes QUEUE_DB_DIR env var', async () => {
        const { startBackend } = await import('../backend')
        const cp = await import('child_process')
        await startBackend()
        const opts = (cp.spawn as ReturnType<typeof vi.fn>).mock.calls[0][2] as { env: Record<string, string> }
        expect(opts.env.QUEUE_DB_DIR).toBeDefined()
    })

    it('spawns with detached: true', async () => {
        const { startBackend } = await import('../backend')
        const cp = await import('child_process')
        await startBackend()
        const opts = (cp.spawn as ReturnType<typeof vi.fn>).mock.calls[0][2] as { detached: boolean }
        expect(opts.detached).toBe(true)
    })

    it('returns the dynamic port as a number', async () => {
        const { startBackend } = await import('../backend')
        const port = await startBackend()
        expect(typeof port).toBe('number')
        expect(port).toBeGreaterThan(0)
    })

    it('reuses an in-flight backend startup instead of spawning a second backend', async () => {
        let releaseFetch: (() => void) | null = null
        vi.stubGlobal('fetch', vi.fn(() => new Promise(resolve => {
            releaseFetch = () => resolve({ ok: true })
        })))

        const { startBackend } = await import('../backend')
        const cp = await import('child_process')

        const first = startBackend()
        const second = startBackend()
        await vi.waitFor(() => expect(releaseFetch).toBeTypeOf('function'))
        releaseFetch?.()

        await expect(Promise.all([first, second])).resolves.toEqual([9100, 9100])
        expect(cp.spawn).toHaveBeenCalledTimes(1)
    })

    it('reuses an already-running backend process instead of spawning a second backend', async () => {
        const { startBackend } = await import('../backend')
        const cp = await import('child_process')

        await expect(startBackend()).resolves.toBe(9100)
        await expect(startBackend()).resolves.toBe(9100)

        expect(cp.spawn).toHaveBeenCalledTimes(1)
    })

    it('reuses an existing packaged Windows backend runtime lock instead of spawning another backend', async () => {
        isPackaged = true
        vi.stubGlobal('process', { ...process, platform: 'win32', resourcesPath: 'C:\\mock\\resources' })
        const existsError = new Error('exists') as NodeJS.ErrnoException
        existsError.code = 'EEXIST'
        openSyncMock.mockImplementation(() => { throw existsError })
        readFileSyncMock.mockReturnValue('9100')

        const { startBackend } = await import('../backend')
        const cp = await import('child_process')

        await expect(startBackend()).resolves.toBe(9100)

        expect(cp.spawn).not.toHaveBeenCalled()
        expect(execFileMock).not.toHaveBeenCalled()
        expect(unlinkSyncMock).not.toHaveBeenCalled()
    })
})

// -----------------------------------------------------------------------
// stopBackend
// -----------------------------------------------------------------------
describe('stopBackend', () => {
    it('calls process.kill with negative pid (SIGTERM)', async () => {
        const killSpy = vi.spyOn(process, 'kill').mockImplementation(() => true)
        const { startBackend, stopBackend } = await import('../backend')
        await startBackend()
        stopBackend()
        expect(killSpy).toHaveBeenCalledWith(-mockSpawnProcess.pid, 'SIGTERM')
    })

    it('does not throw if no backend is running', async () => {
        const { stopBackend } = await import('../backend')
        expect(() => stopBackend()).not.toThrow()
    })
})

// -----------------------------------------------------------------------
// waitForBackend
// -----------------------------------------------------------------------
describe('waitForBackend', () => {
    it('resolves when fetch returns ok after initial failure', async () => {
        vi.stubGlobal('fetch', vi.fn()
            .mockResolvedValueOnce({ ok: false })
            .mockResolvedValueOnce({ ok: true })
        )
        const { waitForBackend } = await import('../backend')
        await expect(waitForBackend(9100, 5)).resolves.toBeUndefined()
    })

    it('rejects after max retries when fetch always fails', async () => {
        vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('ECONNREFUSED')))
        const { waitForBackend } = await import('../backend')
        await expect(waitForBackend(9100, 2)).rejects.toThrow()
    })
})

// -----------------------------------------------------------------------
// getBackendPort
// -----------------------------------------------------------------------
describe('getBackendPort', () => {
    it('returns null before startBackend is called', async () => {
        const { getBackendPort } = await import('../backend')
        expect(getBackendPort()).toBeNull()
    })

    it('returns the port after startBackend', async () => {
        const { startBackend, getBackendPort } = await import('../backend')
        const port = await startBackend()
        expect(getBackendPort()).toBe(port)
    })

    it('returns null after stopBackend', async () => {
        vi.spyOn(process, 'kill').mockImplementation(() => true)
        const { startBackend, stopBackend, getBackendPort } = await import('../backend')
        await startBackend()
        stopBackend()
        expect(getBackendPort()).toBeNull()
    })
})
