export { }

type Platform = 'win32' | 'darwin' | 'linux'

export interface ElectronAPI {
    openFolder: () => Promise<string | null>
    getBackendPort: () => Promise<number>
    onBackendReady: (cb: (port: number) => void) => void
    platform: Platform

    // Setup wizard — invoke channels
    checkSetupNeeded: () => Promise<{ needed: boolean }>
    installDeps: () => Promise<void>
    initDb: () => Promise<void>
    downloadModel: (payload: { modelId: string }) => Promise<void>
    cancelDownload: () => Promise<void>
    completeSetup: (payload?: { skippedModels?: string[] }) => Promise<void>
    uninstall: () => Promise<{ cancelled: true } | { success: true }>

    // Setup wizard — event subscriptions (main→renderer)
    onInstallDepsProgress: (cb: (data: { line: string; percent: number }) => void) => void
    onDownloadModelProgress: (cb: (data: { modelId: string; percent: number; bytes: number }) => void) => void
}

declare global {
    interface Window {
        electronAPI: ElectronAPI
    }
}
