import { app, nativeImage, protocol, net } from 'electron'
import { createHash } from 'crypto'
import { mkdir, stat, writeFile } from 'fs/promises'
import path from 'path'
import { pathToFileURL } from 'url'

const DEFAULT_THUMB_WIDTH = 360
const DEFAULT_THUMB_HEIGHT = 270

function parsePositiveInt(value: string | null, fallback: number): number {
    if (!value) return fallback
    const parsed = Number.parseInt(value, 10)
    return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback
}

function thumbnailCachePath(filePath: string, mtimeMs: number, width: number, height: number): string {
    const key = createHash('sha256')
        .update(filePath)
        .update('\0')
        .update(String(Math.round(mtimeMs)))
        .update('\0')
        .update(`${width}x${height}`)
        .digest('hex')
    return path.join(app.getPath('userData'), 'thumbnail-cache', `${key}.png`)
}

async function getThumbnailPath(filePath: string, width: number, height: number): Promise<string | null> {
    const sourceStat = await stat(filePath)
    const cachePath = thumbnailCachePath(filePath, sourceStat.mtimeMs, width, height)

    try {
        await stat(cachePath)
        return cachePath
    } catch {
        // Cache miss — generate below.
    }

    let image = await nativeImage.createThumbnailFromPath(filePath, { width, height })
    if (image.isEmpty()) {
        const original = nativeImage.createFromPath(filePath)
        if (original.isEmpty()) return null
        image = original.resize({ width, height, quality: 'good' })
    }

    await mkdir(path.dirname(cachePath), { recursive: true })
    await writeFile(cachePath, image.toPNG())
    return cachePath
}

export function registerAppProtocol(): void {
    protocol.handle('app', async (request) => {
        const url = new URL(request.url)
        const filePath = url.searchParams.get('path')
        if (!filePath) return net.fetch('file://')

        const thumbnail = url.searchParams.get('thumbnail') === '1'
        if (thumbnail) {
            try {
                const width = parsePositiveInt(url.searchParams.get('width'), DEFAULT_THUMB_WIDTH)
                const height = parsePositiveInt(url.searchParams.get('height'), DEFAULT_THUMB_HEIGHT)
                const thumbPath = await getThumbnailPath(filePath, width, height)
                if (thumbPath) return net.fetch(pathToFileURL(thumbPath).toString())
            } catch {
                // Fall back to the original image when thumbnail generation fails.
            }
        }

        // pathToFileURL correctly percent-encodes spaces and special characters
        // that would otherwise produce an invalid file:// URL and silently break
        // image loading for photos stored in folders with spaces in their names.
        return net.fetch(pathToFileURL(filePath).toString())
    })
}
