import { app, BrowserWindow } from 'electron'
import { existsSync } from 'fs'
import { join } from 'path'
import { registerIpcHandlers } from './ipc'
import { registerAppProtocol } from './protocol'
import { startBackend, stopBackend, waitForBackend } from './backend'

app.setName('PhotoDescriber2')

let mainWindow: BrowserWindow | null = null

function createMainWindow(): BrowserWindow {
    const win = new BrowserWindow({
        width: 1280,
        height: 820,
        show: false,
        webPreferences: {
            preload: join(__dirname, '../preload/index.js'),
            contextIsolation: true,
            nodeIntegration: false,
        },
    })

    if (!app.isPackaged) {
        win.loadURL('http://127.0.0.1:5173')
        win.webContents.openDevTools()
    } else {
        win.loadFile(join(__dirname, '../renderer/index.html'))
    }

    win.once('ready-to-show', () => win.show())
    return win
}

app.whenReady().then(async () => {
    registerAppProtocol()

    const setupDone = existsSync(join(app.getPath('userData'), 'setup_done'))

    if (!setupDone) {
        // First run: show window immediately so the setup wizard can run.
        // Backend will be started by setup:complete once the wizard finishes.
        registerIpcHandlers(0)
        mainWindow = createMainWindow()
        return
    }

    // Setup already done: start backend, then open window.
    try {
        const port = await startBackend()
        await waitForBackend(port)
        registerIpcHandlers(port)
        mainWindow = createMainWindow()
    } catch (err) {
        console.error('[startup] Failed to start backend:', err)
        app.quit()
    }
})

app.on('will-quit', () => {
    stopBackend()
})

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit()
})
