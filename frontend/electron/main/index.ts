import { app, BrowserWindow, dialog } from 'electron'
import { join } from 'path'
import { registerIpcHandlers } from './ipc'
import { registerAppProtocol } from './protocol'
import { getBackendSetupIssue, startBackend, stopBackend } from './backend'

app.setName('PhotoRAG')

 
let mainWindow: BrowserWindow | null = null
const gotSingleInstanceLock = app.requestSingleInstanceLock()

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

if (!gotSingleInstanceLock) {
    app.quit()
} else {
    app.on('second-instance', () => {
        if (!mainWindow) return
        if (mainWindow.isMinimized()) mainWindow.restore()
        mainWindow.focus()
    })

    app.whenReady().then(async () => {
        registerAppProtocol()

        const setupIssue = getBackendSetupIssue()

        if (setupIssue) {
            console.warn(`[startup] Setup wizard required: ${setupIssue}`)
            // First run or stale setup: show the wizard so it can repair userData.
            // Backend will be started by setup:complete once the wizard finishes.
            registerIpcHandlers(0)
            mainWindow = createMainWindow()
            return
        }

        // Setup already done: start backend, then open window.
        try {
            const port = await startBackend()
            registerIpcHandlers(port)
            mainWindow = createMainWindow()
        } catch (err) {
            console.error('[startup] Failed to start backend:', err)
            dialog.showErrorBox(
                'PhotoRAG — startup error',
                `The Python backend failed to start.\n\n${err instanceof Error ? err.message : String(err)}\n\nCheck that the installation completed successfully via the Setup Wizard.`
            )
            app.quit()
        }
    })

    app.on('will-quit', () => {
        stopBackend()
    })

    app.on('window-all-closed', () => {
        if (process.platform !== 'darwin') app.quit()
    })
}
