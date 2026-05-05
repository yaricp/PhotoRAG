let _port: number | null = null

export async function getBaseUrl(): Promise<string> {
    if (_port) return `http://localhost:${_port}`

    if (window.electronAPI) {
        _port = await window.electronAPI.getBackendPort()
        return `http://localhost:${_port}`
    }

    return import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
}