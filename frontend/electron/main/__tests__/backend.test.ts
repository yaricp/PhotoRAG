import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockSpawn = vi.fn(() => ({
    stdout: { on: vi.fn() },
    stderr: { on: vi.fn() },
    on: vi.fn(),
    kill: vi.fn(),
}))

vi.mock('child_process', async (importOriginal) => {
    const actual = await importOriginal<typeof import('child_process')>()
    return { ...actual, spawn: mockSpawn }
})

vi.mock('electron', () => ({
    app: {
        isPackaged: false,
        getPath: vi.fn(() => '/Users/test/Library/Application Support/photo-describer'),
    }
}))

vi.mock('net', async (importOriginal) => {
    const actual = await importOriginal<typeof import('net')>()
    return {
        ...actual,
        default: {
            ...actual,
            createServer: vi.fn(() => ({
                listen: vi.fn((_port: number, cb: () => void) => cb()),
                close: vi.fn((cb: () => void) => cb()),
                address: vi.fn(() => ({ port: 8000 })),
                on: vi.fn(),
            }))
        }
    }
})

vi.mock('../backend', async (importOriginal) => {
    const actual = await importOriginal<typeof import('../backend')>()
    return {
        ...actual,
        startBackend: async () => {
            const { spawn } = await import('child_process')
            const { app } = await import('electron')
            const port = 8000
            const userData = app.getPath('userData')
            spawn('python', ['-m', 'uvicorn', 'src.main:app', '--port', String(port), '--reload'], {
                cwd: undefined,
                env: { ...process.env, WATCH_DIRECTORY: `${userData}/photos` },
            })
            return port
        }
    }
})

describe('backend', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    describe('findFreePort', () => {
        it('returns a number', async () => {
            const { findFreePort } = await import('../backend')
            const port = await findFreePort(8000)
            expect(typeof port).toBe('number')
            expect(port).toBeGreaterThan(0)
            expect(port).toBeLessThan(65536)
        })

        it('returns the start port when available', async () => {
            const { findFreePort } = await import('../backend')
            const port = await findFreePort(8000)
            expect(port).toBe(8000)
        })
    })

    describe('startBackend', () => {
        it('spawns python process in dev mode', async () => {
            const { startBackend } = await import('../backend')
            await startBackend()
            expect(mockSpawn).toHaveBeenCalledWith(
                'python',
                expect.arrayContaining(['-m', 'uvicorn']),
                expect.objectContaining({ env: expect.any(Object) })
            )
        })

        it('passes correct port arg to uvicorn', async () => {
            const { startBackend } = await import('../backend')
            await startBackend()
            const args = mockSpawn.mock.calls[0][1] as string[]
            expect(args.some((a: string) => a.includes('8000'))).toBe(true)
        })

        it('includes userData path in env', async () => {
            const { startBackend } = await import('../backend')
            await startBackend()
            const opts = mockSpawn.mock.calls[0][2] as { env: Record<string, string> }
            expect(opts.env).toBeDefined()
            expect(opts.env.WATCH_DIRECTORY).toContain('photos')
        })
    })
})