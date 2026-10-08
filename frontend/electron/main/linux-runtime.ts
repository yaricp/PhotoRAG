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
    env: NodeJS.ProcessEnv,
): void {
    if (!app.isPackaged || platform !== 'linux') return

    // The packaged UI does not need hardware acceleration. Some Linux GPU
    // drivers fail Electron's command-buffer setup before the first window is shown.
    if (!app.commandLine.hasSwitch('disable-gpu') && !app.commandLine.hasSwitch('enable-gpu')) {
        app.commandLine.appendSwitch('disable-gpu')
        console.info('[startup] Linux packaged app: using software rendering')
    }

    // Prefer X11/XWayland when available. Native Wayland startup can leave the
    // hidden first window waiting forever on some desktop/compositor combinations.
    if (
        env.DISPLAY &&
        !app.commandLine.hasSwitch('ozone-platform') &&
        !app.commandLine.hasSwitch('ozone-platform-hint')
    ) {
        app.commandLine.appendSwitch('ozone-platform', 'x11')
        console.info('[startup] Linux display detected; using X11 for window rendering')
    }
}
