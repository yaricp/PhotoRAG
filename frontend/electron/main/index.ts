import { app, BrowserWindow, dialog, shell } from 'electron'
import { join } from 'path'
import { registerIpcHandlers } from './ipc'
import { registerAppProtocol } from './protocol'
import { getBackendSetupIssue, startBackend, stopBackend } from './backend'
import { ensureLinuxAppMenuEntry } from './linux-launcher'

app.setName('PhotoRAG')

// Some packaged Linux builds can start under Wayland without ever showing the
// hidden startup window. Use XWayland when the session exposes both displays;
// keep native Wayland for systems without XWayland and honor explicit flags.
if (
    app.isPackaged &&
    process.platform === 'linux' &&
    process.env.WAYLAND_DISPLAY &&
    process.env.DISPLAY &&
    !app.commandLine.hasSwitch('ozone-platform') &&
    !app.commandLine.hasSwitch('ozone-platform-hint')
) {
    app.commandLine.appendSwitch('ozone-platform', 'x11')
    console.info('[startup] Wayland session detected; using XWayland for this packaged Linux run')
}

 
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

    win.webContents.setWindowOpenHandler(({ url }) => {
        if (url.startsWith('https://') || url.startsWith('http://')) void shell.openExternal(url)
        return { action: 'deny' }
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
        void ensureLinuxAppMenuEntry()

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
