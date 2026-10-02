import { describe, it, expect, vi } from 'vitest'

const mockHandle = vi.fn()
const mockShowOpenDialog = vi.fn()
const mockGetVersion = vi.fn(() => '0.1.5-pre.9')

vi.mock('electron', () => ({
    ipcMain: { handle: mockHandle },
    dialog: { showOpenDialog: mockShowOpenDialog },
    app: { getVersion: mockGetVersion },
}))

describe('ipc', () => {
    it('registers select-folder and get-backend-port handlers', async () => {
        mockHandle.mockClear()
        const { registerIpcHandlers } = await import('../ipc')
        registerIpcHandlers(8000)
        const channels = mockHandle.mock.calls.map((c) => c[0])
        expect(channels).toContain('select-folder')
        expect(channels).toContain('get-backend-port')
        expect(channels).toContain('app:get-version')
    })

    it('returns the version reported by Electron', async () => {
        mockHandle.mockClear()
        const { registerIpcHandlers } = await import('../ipc')
        registerIpcHandlers(8000)
        const versionHandler = mockHandle.mock.calls.find((c) => c[0] === 'app:get-version')?.[1]
        expect(versionHandler?.({} as any)).toBe('0.1.5-pre.9')
    })

    it('get-backend-port handler returns the port passed in', async () => {
        mockHandle.mockClear()
        const { registerIpcHandlers } = await import('../ipc')
        registerIpcHandlers(9001)
        const portHandler = mockHandle.mock.calls.find((c) => c[0] === 'get-backend-port')?.[1]
        const result = await portHandler?.({} as any)
        expect(result).toBe(9001)
    })

    it('select-folder returns null when dialog cancelled', async () => {
        mockHandle.mockClear()
        mockShowOpenDialog.mockResolvedValue({ canceled: true, filePaths: [] })
        const { registerIpcHandlers } = await import('../ipc')
        registerIpcHandlers(8000)
        const folderHandler = mockHandle.mock.calls.find((c) => c[0] === 'select-folder')?.[1]
        const result = await folderHandler?.({} as any)
        expect(result).toBeNull()
    })

    it('select-folder returns path when dialog confirmed', async () => {
        mockHandle.mockClear()
        mockShowOpenDialog.mockResolvedValue({ canceled: false, filePaths: ['/Users/test/Photos'] })
        const { registerIpcHandlers } = await import('../ipc')
        registerIpcHandlers(8000)
        const folderHandler = mockHandle.mock.calls.find((c) => c[0] === 'select-folder')?.[1]
        const result = await folderHandler?.({} as any)
        expect(result).toBe('/Users/test/Photos')
    })
})
