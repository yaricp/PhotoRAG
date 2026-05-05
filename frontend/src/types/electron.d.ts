interface ElectronAPI {
    openFolder: () => Promise<string | null>
    getBackendPort: () => Promise<number>
    onBackendReady: (cb: (port: number) => void) => void
    platform: NodeJS.Platform
}

declare global {
    interface Window {
        electronAPI?: ElectronAPI
    }
}

export { }