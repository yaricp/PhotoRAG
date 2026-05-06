import { ipcMain, dialog } from 'electron'

export function registerIpcHandlers(backendPort: number): void {
    console.log('[IPC] registering handlers, port =', backendPort)

    ipcMain.handle('select-folder', async () => {
        const result = await dialog.showOpenDialog({
            properties: ['openDirectory'],
            title: 'Select Photos Folder',
        })
        return result.canceled ? null : result.filePaths[0]
    })

    console.log('[IPC] registering get-backend-port')
    ipcMain.handle('get-backend-port', () => backendPort)
    console.log('[IPC] done')
}