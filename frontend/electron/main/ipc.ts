import { ipcMain, dialog, app } from 'electron'
import { existsSync } from 'fs'
import { join } from 'path'

export function registerIpcHandlers(backendPort: number): void {
    console.log('[IPC] registering handlers, port =', backendPort)

    ipcMain.handle('select-folder', async () => {
        const result = await dialog.showOpenDialog({
            properties: ['openDirectory'],
            title: 'Select Photos Folder',
        })
        return result.canceled ? null : result.filePaths[0]
    })

    ipcMain.handle('get-backend-port', () => backendPort)

    // Check whether first-run setup wizard is needed (venv not yet created).
    ipcMain.handle('setup:check-needed', () => {
        const venvPath = join(app.getPath('userData'), 'venv')
        return { needed: !existsSync(venvPath) }
    })

    console.log('[IPC] done')
}
