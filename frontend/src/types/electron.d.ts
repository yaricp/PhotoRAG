export { }

type Platform = 'win32' | 'darwin' | 'linux'

export interface ElectronAPI {
    openFolder: () => Promise<string | null>
    getBackendPort: () => Promise<number>
    onBackendReady: (cb: (port: number) => void) => void
    platform: Platform
}

declare global {
    interface Window {
        electronAPI: ElectronAPI
    }
}