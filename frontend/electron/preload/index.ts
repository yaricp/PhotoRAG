import { contextBridge, ipcRenderer } from 'electron'

console.log('[PRELOAD] LOADED')

contextBridge.exposeInMainWorld('electronAPI', {
    openFolder: () => ipcRenderer.invoke('select-folder'),
    getBackendPort: () => ipcRenderer.invoke('get-backend-port'),
    onBackendReady: (cb: (port: number) => void) => {
        ipcRenderer.on('backend-ready', (_, port) => cb(port))
    },
    platform: process.platform,

    // Setup wizard — invoke channels
    checkSetupNeeded: () => ipcRenderer.invoke('setup:check-needed'),
    installDeps: () => ipcRenderer.invoke('setup:install-deps'),
    initDb: () => ipcRenderer.invoke('setup:init-db'),
    downloadModel: (payload: { modelId: string }) => ipcRenderer.invoke('setup:download-model', payload),
    cancelDownload: () => ipcRenderer.invoke('setup:cancel-download'),
    completeSetup: (payload?: { skippedModels?: string[] }) => ipcRenderer.invoke('setup:complete', payload),
    uninstall: () => ipcRenderer.invoke('app:uninstall'),

    // Setup wizard — model config (runs before backend starts, talks to DB directly)
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
