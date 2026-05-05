import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('electron', () => ({
    protocol: {
        handle: vi.fn(),
    },
    net: {
        fetch: vi.fn((url: string) => Promise.resolve(new Response('image data'))),
    }
}))

describe('protocol', () => {
    beforeEach(() => {
        vi.resetModules()
    })

    it('registers handler for "app" scheme', async () => {
        const { protocol } = await import('electron')
        const { registerAppProtocol } = await import('../protocol')

        registerAppProtocol()

        expect(protocol.handle).toHaveBeenCalledWith('app', expect.any(Function))
    })

    it('handler converts app:// URL to file:// URL', async () => {
        const { protocol, net } = await import('electron')
        const { registerAppProtocol } = await import('../protocol')

        registerAppProtocol()

        const handler = vi.mocked(protocol.handle).mock.calls[0][1]
        const filePath = '/Users/test/Photos/img.png'
        const request = new Request(`app://local-image?path=${encodeURIComponent(filePath)}`)

        await handler(request)

        expect(net.fetch).toHaveBeenCalledWith(`file://${filePath}`)
    })

    it('handler with missing path calls fetch with empty file://', async () => {
        const { protocol, net } = await import('electron')
        const { registerAppProtocol } = await import('../protocol')

        registerAppProtocol()

        const handler = vi.mocked(protocol.handle).mock.calls[0][1]
        const request = new Request('app://local-image')

        await handler(request)

        expect(net.fetch).toHaveBeenCalledWith('file://')
    })
})