import { app, BrowserWindow, dialog, shell } from 'electron'
import { join } from 'path'
import { registerIpcHandlers } from './ipc'
import { registerAppProtocol } from './protocol'
import { getBackendSetupIssue, logToFile, startBackend, stopBackend } from './backend'
import { ensureLinuxAppMenuEntry } from './linux-launcher'
import { configureLinuxRuntime } from './linux-runtime'

app.setName('PhotoRAG')
if (process.platform === 'linux') {
    // Match the desktop entry we create in linux-launcher.ts. This is the
    // Linux desktop identity used by Wayland and X11 for taskbar grouping.
    app.setDesktopName('com.photorag.app')
}
configureLinuxRuntime(app, process.platform)

let mainWindow: BrowserWindow | null = null
const gotSingleInstanceLock = app.requestSingleInstanceLock()

function createMainWindow(): BrowserWindow {
    const isPackagedLinux = process.platform === 'linux' && app.isPackaged
    const win = new BrowserWindow({
        width: 1280,
        height: 820,
        // Do not leave Linux users with a running process and only a taskbar
        // entry if the platform never emits ready-to-show (seen with software
        // rendering on some X11/Wayland setups).
        show: process.platform === 'linux',
        title: 'PhotoRAG',
        ...(isPackagedLinux ? { icon: join(process.resourcesPath, 'photorag-icon.png') } : {}),
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

    let rendererFailureReported = false
    const reportRendererFailure = (message: string): void => {
        logToFile(`[window] ${message}`)
        if (rendererFailureReported || win.isDestroyed()) return
        rendererFailureReported = true
        win.show()
        dialog.showErrorBox(
            'PhotoRAG — window startup problem',
            `${message}\n\nDetails were saved to ${join(app.getPath('userData'), 'photorag.log')}`
        )
    }

    logToFile(`[window] creating main window; linux=${process.platform === 'linux'} packaged=${app.isPackaged}`)
    win.webContents.on('did-finish-load', () => {
        logToFile(`[window] renderer finished loading: ${win.webContents.getURL()}`)
        if (!win.isVisible()) {
            logToFile('[window] showing main window after renderer load')
            win.show()
        }
    })
    win.webContents.on('did-fail-load', (_event, errorCode, errorDescription, validatedURL, isMainFrame) => {
        logToFile(`[window] did-fail-load mainFrame=${isMainFrame} code=${errorCode} description=${errorDescription} url=${validatedURL}`)
        if (isMainFrame) {
            reportRendererFailure(`The application window could not load its interface (${errorCode}: ${errorDescription}).`)
        }
    })
    win.webContents.on('render-process-gone', (_event, details) => {
        reportRendererFailure(`The application window stopped unexpectedly (${details.reason}, exit code ${details.exitCode}).`)
    })
    win.webContents.on('console-message', (details) => {
        if (details.level === 'warning' || details.level === 'error') {
            logToFile(`[renderer:${details.level}] ${details.sourceId}:${details.lineNumber} ${details.message}`)
        }
    })

    const rendererPath = join(__dirname, '../renderer/index.html')
    logToFile(`[window] loading renderer: ${rendererPath}`)
    const navigation = !app.isPackaged
        ? win.loadURL('http://127.0.0.1:5173')
        : win.loadFile(rendererPath)
    void navigation.catch((error: unknown) => {
        const message = error instanceof Error ? error.message : String(error)
        reportRendererFailure(`The application window failed to load: ${message}`)
    })

    if (!app.isPackaged) {
        win.webContents.openDevTools()
    }

    win.once('ready-to-show', () => {
        logToFile('[window] ready-to-show received')
        if (!win.isVisible()) win.show()
    })
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

        const shouldContinueFromMenu = await ensureLinuxAppMenuEntry()
        if (shouldContinueFromMenu) {
            if (!process.stdout.isTTY) {
                try {
                    await dialog.showMessageBox({
                        type: 'info',
                        title: 'PhotoRAG is ready',
                        message: 'PhotoRAG was added to the Applications menu.',
                        detail: 'This launch will now close. Open PhotoRAG from the Applications menu to continue setup.',
                        buttons: ['OK'],
                    })
                } catch (error) {
                    logToFile(`[startup] could not show first-launch message: ${error instanceof Error ? error.message : String(error)}`)
                }
            }
            app.quit()
            return
        }

        const setupIssue = getBackendSetupIssue()

        if (setupIssue) {
            logToFile(`[startup] Setup wizard required: ${setupIssue}`)
            console.warn(`[startup] Setup wizard required: ${setupIssue}`)
            // First run or stale setup: show the wizard so it can repair userData.
            // Backend will be started by setup:complete once the wizard finishes.
            registerIpcHandlers(0)
            mainWindow = createMainWindow()
            return
        }

        // Setup already done: start backend, then open window.
        try {
            logToFile('[startup] setup is complete; starting backend')
            const port = await startBackend()
            registerIpcHandlers(port)
            mainWindow = createMainWindow()
        } catch (err) {
            logToFile(`[startup] Failed to start backend: ${err instanceof Error ? err.stack ?? err.message : String(err)}`)
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
