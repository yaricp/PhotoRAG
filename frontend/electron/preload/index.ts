import { contextBridge, ipcRenderer } from 'electron'
console.log('[PRELOAD] LOADED')
contextBridge.exposeInMainWorld('electronAPI', {
    openFolder: () => ipcRenderer.invoke('select-folder'),
    getBackendPort: () => ipcRenderer.invoke('get-backend-port'),
    onBackendReady: (cb: (port: number) => void) => {
        ipcRenderer.on('backend-ready', (_, port) => cb(port))
    },
    platform: process.platform,
})
