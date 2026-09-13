import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

let mockHandle = vi.fn()
let mockSend = vi.fn()
let spawnMock = vi.fn()
let logToFileMock = vi.fn()
let existsSyncMock = vi.fn(() => false)
let openSyncMock = vi.fn(() => 42)
let closeSyncMock = vi.fn()
let unlinkSyncMock = vi.fn()

function mockSuccessfulSpawn({ emitClose = true, emitExit = false } = {}) {
    const stdoutHandlers: Array<(data: Buffer) => void> = []
    const stderrHandlers: Array<(data: Buffer) => void> = []
    const closeHandlers: Array<(code: number) => void> = []
    const exitHandlers: Array<(code: number) => void> = []

    const child = {
        stdout: {
            on: vi.fn((event: string, cb: (data: Buffer) => void) => {
                if (event === 'data') stdoutHandlers.push(cb)
            }),
        },
        stderr: {
            on: vi.fn((event: string, cb: (data: Buffer) => void) => {
                if (event === 'data') stderrHandlers.push(cb)
            }),
        },
        on: vi.fn((event: string, cb: (code: number) => void) => {
            if (event === 'close') closeHandlers.push(cb)
            if (event === 'exit') exitHandlers.push(cb)
        }),
        kill: vi.fn(),
    }

    queueMicrotask(() => {
        stdoutHandlers.forEach(cb => cb(Buffer.from('done\n')))
        stderrHandlers.forEach(cb => cb(Buffer.from('')))
        if (emitExit) exitHandlers.forEach(cb => cb(0))
        if (emitClose) closeHandlers.forEach(cb => cb(0))
    })

    return child
}

beforeEach(() => {
    vi.resetModules()
    vi.stubGlobal('process', { ...process, platform: 'win32', resourcesPath: 'C:\\mock\\resources' })
    mockHandle = vi.fn()
    mockSend = vi.fn()
    logToFileMock = vi.fn()
    existsSyncMock = vi.fn(() => false)
    openSyncMock = vi.fn(() => 42)
    closeSyncMock = vi.fn()
    unlinkSyncMock = vi.fn()
    spawnMock = vi.fn(() => mockSuccessfulSpawn())

    vi.doMock('electron', () => ({
        ipcMain: { handle: mockHandle },
        dialog: { showOpenDialog: vi.fn() },
        shell: { trashItem: vi.fn() },
        app: {
            isPackaged: true,
            getPath: vi.fn(() => 'C:\\Users\\test\\AppData\\Roaming\\PhotoRAG'),
            quit: vi.fn(),
        },
    }))
    vi.doMock('fs', () => ({
        default: {
            closeSync: closeSyncMock,
            existsSync: existsSyncMock,
            openSync: openSyncMock,
            writeFileSync: vi.fn(),
            readFileSync: vi.fn(() => '{}'),
            rmSync: vi.fn(),
            unlinkSync: unlinkSyncMock,
        },
        closeSync: closeSyncMock,
        existsSync: existsSyncMock,
        openSync: openSyncMock,
        writeFileSync: vi.fn(),
        readFileSync: vi.fn(() => '{}'),
        rmSync: vi.fn(),
        unlinkSync: unlinkSyncMock,
    }))
    vi.doMock('fs/promises', () => ({
        default: { cp: vi.fn().mockResolvedValue(undefined) },
        cp: vi.fn().mockResolvedValue(undefined),
    }))
    vi.doMock('child_process', () => ({
        default: { spawn: spawnMock },
        spawn: spawnMock,
    }))
    vi.doMock('../backend', () => ({
        locatePython: vi.fn(() => 'C:\\mock\\resources\\python\\python.exe'),
        locateBackend: vi.fn(() => 'C:\\mock\\resources\\backend'),
        startBackend: vi.fn(),
        waitForBackend: vi.fn(),
        logToFile: logToFileMock,
    }))
})

afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
})

describe('setup:install-deps', () => {
    it('installs requirements through venv python -m pip on Windows', async () => {
        const { registerIpcHandlers } = await import('../ipc')

        registerIpcHandlers(0)
        const installDepsHandler = mockHandle.mock.calls.find(call => call[0] === 'setup:install-deps')?.[1]
        await installDepsHandler({ sender: { send: mockSend } })

        expect(spawnMock).toHaveBeenCalledTimes(2)
        expect(spawnMock.mock.calls[0][1]).toEqual([
            '-m',
            'venv',
            'C:\\Users\\test\\AppData\\Roaming\\PhotoRAG/venv',
        ])
        expect(spawnMock.mock.calls[1][0]).toBe('C:\\Users\\test\\AppData\\Roaming\\PhotoRAG/venv/Scripts/python.exe')
        expect(spawnMock.mock.calls[1][1]).toEqual([
            '-m',
            'pip',
            'install',
            '-r',
            'C:\\mock\\resources\\backend/requirements.txt',
            '--progress-bar',
            'off',
            '--extra-index-url',
            'https://download.pytorch.org/whl/cpu',
        ])
        expect(spawnMock.mock.calls[1][2].env.PIP_NO_INPUT).toBe('1')
        expect(spawnMock.mock.calls[1][2].stdio).toEqual(['ignore', 'pipe', 'pipe'])
        expect(openSyncMock).toHaveBeenCalledWith(
            'C:\\Users\\test\\AppData\\Roaming\\PhotoRAG/setup_install_deps.lock',
            'wx'
        )
        expect(closeSyncMock).toHaveBeenCalledWith(42)
        expect(unlinkSyncMock).toHaveBeenCalledWith(
            'C:\\Users\\test\\AppData\\Roaming\\PhotoRAG/setup_install_deps.lock'
        )
        expect(logToFileMock).toHaveBeenCalledWith(expect.stringContaining('[setup] installing requirements:'))
    })

    it('finishes when pip exits even if stdio close is delayed on Windows', async () => {
        spawnMock
            .mockImplementationOnce(() => mockSuccessfulSpawn())
            .mockImplementationOnce(() => mockSuccessfulSpawn({ emitClose: false, emitExit: true }))

        const { registerIpcHandlers } = await import('../ipc')

        registerIpcHandlers(0)
        const installDepsHandler = mockHandle.mock.calls.find(call => call[0] === 'setup:install-deps')?.[1]
        await expect(installDepsHandler({ sender: { send: mockSend } })).resolves.toBeUndefined()

        expect(mockSend).toHaveBeenCalledWith('setup:install-deps-progress', {
            line: 'Done.',
            percent: 100,
        })
    })

    it('does not start a second pip install when dependency setup is invoked twice', async () => {
        const { registerIpcHandlers } = await import('../ipc')

        registerIpcHandlers(0)
        const installDepsHandler = mockHandle.mock.calls.find(call => call[0] === 'setup:install-deps')?.[1]
        await Promise.all([
            installDepsHandler({ sender: { send: mockSend } }),
            installDepsHandler({ sender: { send: mockSend } }),
        ])

        expect(spawnMock).toHaveBeenCalledTimes(2)
        expect(logToFileMock).toHaveBeenCalledWith(
            '[setup] dependency installation already running; joining existing operation'
        )
    })

    it('does not start pip when another process holds the dependency setup lock', async () => {
        const error = new Error('exists') as NodeJS.ErrnoException
        error.code = 'EEXIST'
        openSyncMock.mockImplementation(() => { throw error })
        existsSyncMock
            .mockReturnValueOnce(true)
            .mockReturnValueOnce(false)

        const { registerIpcHandlers } = await import('../ipc')

        registerIpcHandlers(0)
        const installDepsHandler = mockHandle.mock.calls.find(call => call[0] === 'setup:install-deps')?.[1]
        await installDepsHandler({ sender: { send: mockSend } })

        expect(spawnMock).not.toHaveBeenCalled()
        expect(logToFileMock).toHaveBeenCalledWith(
            expect.stringContaining('dependency installation lock already exists')
        )
    })
})
