import { ipcMain, dialog } from 'electron'

export function registerIpcHandlers(backendPort: number): void {
    ipcMain.handle('open-folder', async () => {
        const result = await dialog.showOpenDialog({
            properties: ['openDirectory'],
            title: 'Select Photos Folder',
        })
        return result.canceled ? null : result.filePaths[0]
    })

    ipcMain.handle('get-backend-port', () => backendPort)
}