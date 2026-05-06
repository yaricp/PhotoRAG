import { app, BrowserWindow, protocol } from 'electron'
import { join } from 'path'
import { registerIpcHandlers } from './ipc'
import { registerAppProtocol } from './protocol'

let mainWindow: BrowserWindow | null = null

async function createWindow() {
    registerIpcHandlers(8000)

    mainWindow = new BrowserWindow({
        width: 1200,
        height: 800,
        webPreferences: {
            preload: join(__dirname, '../preload/index.js'),
            contextIsolation: true,
            nodeIntegration: false
        }
    })

    if (!app.isPackaged) {
        await mainWindow.loadURL('http://127.0.0.1:5173')
        mainWindow.webContents.openDevTools()
    } else {
        await mainWindow.loadFile('dist/index.html')
    }
}

// Протокол нужно регистрировать ДО app.whenReady()
app.whenReady().then(() => {
    registerAppProtocol()
    createWindow()
})

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit()
})