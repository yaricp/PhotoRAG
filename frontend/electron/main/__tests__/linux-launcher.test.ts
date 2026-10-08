import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const appImagePath = '/home/test/Downloads/PhotoRAG-0.1.5-x86_64.AppImage'
const applicationCopy = '/home/test/Applications/PhotoRAG.AppImage'
let existsSyncMock: ReturnType<typeof vi.fn>
let writeFileSyncMock: ReturnType<typeof vi.fn>
let linkSyncMock: ReturnType<typeof vi.fn>
let renameSyncMock: ReturnType<typeof vi.fn>
let chmodSyncMock: ReturnType<typeof vi.fn>
let copyFileMock: ReturnType<typeof vi.fn>
let logToFileMock: ReturnType<typeof vi.fn>

beforeEach(() => {
    vi.resetModules()
    vi.stubGlobal('process', {
        ...process,
        platform: 'linux',
        resourcesPath: '/app/resources',
        env: { ...process.env, APPIMAGE: appImagePath, XDG_DATA_HOME: undefined },
    })

    existsSyncMock = vi.fn((path: string) => path === appImagePath)
    writeFileSyncMock = vi.fn()
    linkSyncMock = vi.fn()
    renameSyncMock = vi.fn()
    chmodSyncMock = vi.fn()
    copyFileMock = vi.fn().mockResolvedValue(undefined)
    logToFileMock = vi.fn()

    const fsMock = {
        chmodSync: chmodSyncMock,
        copyFileSync: vi.fn(),
        existsSync: existsSyncMock,
        linkSync: linkSyncMock,
        mkdirSync: vi.fn(),
        readFileSync: vi.fn(() => {
            const error = new Error('missing metadata') as NodeJS.ErrnoException
            error.code = 'ENOENT'
            throw error
        }),
        renameSync: renameSyncMock,
        statSync: vi.fn(() => ({ size: 1234, mtimeMs: 4567 })),
        unlinkSync: vi.fn(),
        writeFileSync: writeFileSyncMock,
    }

    vi.doMock('fs', () => ({ default: fsMock, ...fsMock }))
    vi.doMock('fs/promises', () => ({ default: { copyFile: copyFileMock }, copyFile: copyFileMock }))

    const appMock = {
        isPackaged: true,
        getPath: vi.fn(() => '/home/test'),
        getVersion: vi.fn(() => '0.1.5'),
        commandLine: {
            hasSwitch: vi.fn(() => false),
            getSwitchValue: vi.fn(() => ''),
        },
    }
    vi.doMock('electron', () => ({ default: { app: appMock }, app: appMock }))
    vi.doMock('../backend', () => ({ logToFile: logToFileMock }))
})

afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
})

describe('ensureLinuxAppMenuEntry', () => {
    it('keeps a persistent AppImage in ~/Applications and points the menu entry to it', async () => {
        const { ensureLinuxAppMenuEntry } = await import('../linux-launcher')

        await ensureLinuxAppMenuEntry()

        expect(linkSyncMock).toHaveBeenCalledWith(
            appImagePath,
            expect.stringMatching(/^\/home\/test\/Applications\/PhotoRAG\.AppImage\.tmp-/)
        )
        expect(renameSyncMock).toHaveBeenCalledWith(
            expect.stringMatching(/^\/home\/test\/Applications\/PhotoRAG\.AppImage\.tmp-/),
            applicationCopy
        )
        expect(writeFileSyncMock).toHaveBeenCalledWith(
            '/home/test/.local/share/applications/com.photorag.app.desktop',
            expect.stringContaining(`Exec="${applicationCopy}"`),
            { mode: 0o755 }
        )
    })

    it('copies the AppImage when hard links are unavailable', async () => {
        linkSyncMock.mockImplementation(() => {
            const error = new Error('different filesystem') as NodeJS.ErrnoException
            error.code = 'EXDEV'
            throw error
        })
        const { ensureLinuxAppMenuEntry } = await import('../linux-launcher')

        await ensureLinuxAppMenuEntry()

        const temporary = expect.stringMatching(/^\/home\/test\/Applications\/PhotoRAG\.AppImage\.tmp-/)
        expect(copyFileMock).toHaveBeenCalledWith(appImagePath, temporary)
        expect(chmodSyncMock).toHaveBeenCalledWith(temporary, 0o755)
        expect(renameSyncMock).toHaveBeenCalledWith(temporary, applicationCopy)
    })
})
