export function photoImageUrl(filePath: string): string {
    if (window.electronAPI) {
        return `app://local-image?path=${encodeURIComponent(filePath)}`
    }
    return `/api/static?path=${encodeURIComponent(filePath)}`
}