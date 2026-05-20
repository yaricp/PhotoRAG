import { protocol, net } from 'electron'
import { pathToFileURL } from 'url'

export function registerAppProtocol(): void {
    protocol.handle('app', (request) => {
        const url = new URL(request.url)
        const filePath = url.searchParams.get('path') ?? ''
        // pathToFileURL correctly percent-encodes spaces and special characters
        // that would otherwise produce an invalid file:// URL and silently break
        // image loading for photos stored in folders with spaces in their names.
        return net.fetch(pathToFileURL(filePath).toString())
    })
}
