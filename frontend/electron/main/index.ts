import { app, BrowserWindow } from 'electron'
import { join } from 'path'
import { registerIpcHandlers } from './ipc'
import { registerAppProtocol } from './protocol'
import { startBackend, stopBackend, waitForBackend } from './backend'

// Force the correct userData path in dev mode (Electron defaults to "Electron")
app.setName('PhotoDescriber2')

let mainWindow: BrowserWindow | null = null
let splashWindow: BrowserWindow | null = null

function createSplash(): BrowserWindow {
    const splash = new BrowserWindow({
        width: 400,
        height: 220,
        frame: false,
        resizable: false,
        center: true,
        show: false,
        webPreferences: { nodeIntegration: false, contextIsolation: true },
    })
    splash.loadFile(join(__dirname, '../../resources/splash.html'))
    splash.once('ready-to-show', () => splash.show())
    return splash
}

async function createMainWindow(port: number) {
    registerIpcHandlers(port)

    mainWindow = new BrowserWindow({
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
        await mainWindow.loadURL('http://127.0.0.1:5173')
        mainWindow.webContents.openDevTools()
    } else {
        await mainWindow.loadFile(join(__dirname, '../../dist/index.html'))
    }

    mainWindow.once('ready-to-show', () => {
        splashWindow?.close()
        splashWindow = null
        mainWindow?.show()
    })
}

app.whenReady().then(async () => {
    registerAppProtocol()

    splashWindow = createSplash()

    try {
        const port = await startBackend()
        await waitForBackend(port)
        await createMainWindow(port)
    } catch (err) {
        console.error('[startup] Failed to start backend:', err)
        splashWindow?.close()
        app.quit()
    }
})

app.on('will-quit', () => {
    stopBackend()
})

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit()
})
