export interface PhotoImageUrlOptions {
    thumbnail?: boolean
    width?: number
    height?: number
}

function appendImageParams(params: URLSearchParams, options: PhotoImageUrlOptions = {}) {
    if (!options.thumbnail) return
    params.set('thumbnail', '1')
    if (options.width) params.set('width', String(options.width))
    if (options.height) params.set('height', String(options.height))
}

export function photoImageUrl(filePath: string, options: PhotoImageUrlOptions = {}): string {
    const params = new URLSearchParams()
    params.set('path', filePath)
    appendImageParams(params, options)

    if (window.electronAPI) {
        return `app://local-image?${params.toString()}`
    }
    return `/api/static?${params.toString()}`
}

export function photoThumbnailUrl(filePath: string): string {
    return photoImageUrl(filePath, { thumbnail: true, width: 360, height: 270 })
}
