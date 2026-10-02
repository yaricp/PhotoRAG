import { contextBridge, ipcRenderer } from 'electron'

console.log('[PRELOAD] LOADED')

contextBridge.exposeInMainWorld('electronAPI', {
    openFolder: () => ipcRenderer.invoke('select-folder'),
    getBackendPort: () => ipcRenderer.invoke('get-backend-port'),
    getAppVersion: () => ipcRenderer.invoke('app:get-version'),
    onBackendReady: (cb: (port: number) => void) => {
        ipcRenderer.on('backend-ready', (_, port) => cb(port))
    },
    platform: process.platform,
    listOllamaModels: (url?: string) => ipcRenderer.invoke('ollama:list-models', url),
    getOllamaInventory: (url?: string) => ipcRenderer.invoke('ollama:inventory', url),
    deleteOllamaModel: (payload: { model: string; url?: string }) => ipcRenderer.invoke('ollama:delete-model', payload),
    pullOllamaModel: (payload: { model: string; url?: string }) => ipcRenderer.invoke('ollama:pull-model', payload),
    cancelOllamaPulls: () => ipcRenderer.invoke('ollama:cancel-pulls'),
    onOllamaPullProgress: (cb: (data: { model: string; status: string; total: number; completed: number; done: boolean }) => void) => {
        const listener = (_: unknown, data: { model: string; status: string; total: number; completed: number; done: boolean }) => cb(data)
        ipcRenderer.on('ollama:pull-progress', listener)
        return () => { ipcRenderer.removeListener('ollama:pull-progress', listener) }
    },

    // Setup wizard — invoke channels
    checkSetupNeeded: () => ipcRenderer.invoke('setup:check-needed'),
    installDeps: () => ipcRenderer.invoke('setup:install-deps'),
    initDb: () => ipcRenderer.invoke('setup:init-db'),
    downloadModel: (payload: { modelId: string }) => ipcRenderer.invoke('setup:download-model', payload),
    cancelDownload: () => ipcRenderer.invoke('setup:cancel-download'),
    completeSetup: (payload?: { skippedModels?: string[]; language?: string }) => ipcRenderer.invoke('setup:complete', payload),
    uninstall: () => ipcRenderer.invoke('app:uninstall'),

    // Setup wizard — model config and status (runs before backend starts)
    getModelStatuses: () => ipcRenderer.invoke('setup:get-model-statuses'),
    getModelConfigs: () => ipcRenderer.invoke('setup:get-model-configs'),
    saveModelConfigs: (configs: any[]) => ipcRenderer.invoke('setup:save-model-configs', configs),

    // Setup wizard — event subscriptions (main→renderer)
    onInstallDepsProgress: (cb: (data: { line: string; percent: number }) => void) => {
        ipcRenderer.on('setup:install-deps-progress', (_, data) => cb(data))
    },
    onDownloadModelProgress: (cb: (data: { modelId: string; percent: number; bytes: number }) => void) => {
        ipcRenderer.on('setup:download-model-progress', (_, data) => cb(data))
    },
})
