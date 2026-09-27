export { }

type Platform = 'win32' | 'darwin' | 'linux'

interface ModelConfigBrief {
    id: number
    type: string
    mode: 'local' | 'remote'
    model_name: string
    url?: string
    api_key?: string
    model_provider?: string
    similarity_limit?: number
}

export interface ElectronAPI {
    openFolder: () => Promise<string | null>
    getBackendPort: () => Promise<number>
    onBackendReady: (cb: (port: number) => void) => void
    platform: Platform
    listOllamaModels: (url?: string) => Promise<string[]>
    getOllamaInventory: (url?: string) => Promise<{
        models: Array<{ name: string; size: number; digest: string }>
        storagePath: string | null; freeBytes: number | null; totalBytes: number | null; storageVerified: boolean
    }>
    deleteOllamaModel: (payload: { model: string; url?: string }) => Promise<void>
    pullOllamaModel: (payload: { model: string; url?: string }) => Promise<void>
    cancelOllamaPulls: () => Promise<void>
    onOllamaPullProgress: (cb: (data: { model: string; status: string; total: number; completed: number; done: boolean }) => void) => () => void

    // Setup wizard — invoke channels
    checkSetupNeeded: () => Promise<{ needed: boolean }>
    installDeps: () => Promise<void>
    initDb: () => Promise<void>
    downloadModel: (payload: { modelId: string }) => Promise<void>
    cancelDownload: () => Promise<void>
    completeSetup: (payload?: { skippedModels?: string[] }) => Promise<void>
    uninstall: () => Promise<{ cancelled: true } | { success: true }>

    // Setup wizard — model config (talks to DB directly, before backend starts)
    getModelConfigs: () => Promise<ModelConfigBrief[]>
    saveModelConfigs: (configs: ModelConfigBrief[]) => Promise<void>

    // Setup wizard — event subscriptions (main→renderer)
    onInstallDepsProgress: (cb: (data: { line: string; percent: number; phase?: string; installedCount?: number; totalCount?: number; latestInstalled?: string; latestPackage?: string }) => void) => void
    onDownloadModelProgress: (cb: (data: { modelId: string; percent: number; bytes: number }) => void) => void
}

declare global {
    interface Window {
        electronAPI: ElectronAPI
    }
}
