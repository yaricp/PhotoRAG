import { app, BrowserWindow } from 'electron'
import { join } from 'path'

let win: BrowserWindow | null = null

function createWindow() {
    win = new BrowserWindow({
        width: 1200,
        height: 800,
        webPreferences: {
            preload: join(__dirname, '../preload/index.js'),
            contextIsolation: true,
            nodeIntegration: false
        }
    })

    const devUrl = 'http://127.0.0.1:5173'

    // 🔥 ЖЁСТКИЙ DEV MODE (без env вообще)
    win.loadURL(devUrl)

    win.webContents.openDevTools()

    win.on('closed', () => {
        win = null
    })
}

app.whenReady().then(createWindow)

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit()
})