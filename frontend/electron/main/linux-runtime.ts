interface RuntimeCommandLine {
    hasSwitch(name: string): boolean
    appendSwitch(name: string, value?: string): void
}

interface RuntimeApp {
    isPackaged: boolean
    commandLine: RuntimeCommandLine
}

/** Apply the Linux desktop defaults that prevent a packaged window from staying hidden. */
export function configureLinuxRuntime(
    app: RuntimeApp,
    platform: NodeJS.Platform,
): void {
    if (!app.isPackaged || platform !== 'linux') return

    // The packaged UI does not need hardware acceleration. Some Linux GPU
    // drivers fail Electron's command-buffer setup before the first window is shown.
    if (!app.commandLine.hasSwitch('disable-gpu') && !app.commandLine.hasSwitch('enable-gpu')) {
        app.commandLine.appendSwitch('disable-gpu')
        console.info('[startup] Linux packaged app: using software rendering')
    }

    // Use the X11 mode that successfully displays the first-run window. Relying
    // on DISPLAY to select it is unreliable in some launch environments.
    if (
        !app.commandLine.hasSwitch('ozone-platform') &&
        !app.commandLine.hasSwitch('ozone-platform-hint')
    ) {
        app.commandLine.appendSwitch('ozone-platform', 'x11')
        console.info('[startup] Linux packaged app: using X11 for window rendering')
    }
}
