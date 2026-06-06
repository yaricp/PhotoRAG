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
const userData = '/Users/test/Library/Application Support/PhotoRAG'

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

    // Register mocks for fresh imports to pick up.
    // Node built-in mocks need a `default` export for Vitest's ESM interop.
    const spawnMock = vi.fn(() => mockSpawnProcess)
    vi.doMock('child_process', () => ({
        default: { spawn: spawnMock },
        spawn: spawnMock,
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
        default: { existsSync: vi.fn(() => false), appendFileSync: vi.fn(), mkdirSync: vi.fn() },
        existsSync: vi.fn(() => false),
        appendFileSync: vi.fn(),
        mkdirSync: vi.fn(),
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
