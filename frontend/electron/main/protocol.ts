import { protocol, net } from 'electron'

export function registerAppProtocol(): void {
    protocol.handle('app', (request) => {
        const url = new URL(request.url)
        const filePath = url.searchParams.get('path') ?? ''
        return net.fetch(`file://${filePath}`)
    })
}