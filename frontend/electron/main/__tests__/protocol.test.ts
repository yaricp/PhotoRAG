import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mkdtemp, writeFile } from 'fs/promises'
import { tmpdir } from 'os'
import path from 'path'

vi.mock('electron', () => ({
    app: {
        getPath: vi.fn(() => path.join(tmpdir(), 'photorag-protocol-test')),
    },
    nativeImage: {
        createThumbnailFromPath: vi.fn(() => Promise.resolve({
            isEmpty: () => false,
            toPNG: () => Buffer.from('thumb data'),
        })),
        createFromPath: vi.fn(() => ({
            isEmpty: () => false,
            resize: () => ({
                isEmpty: () => false,
                toPNG: () => Buffer.from('fallback thumb data'),
            }),
        })),
    },
    protocol: {
        handle: vi.fn(),
    },
    net: {
        fetch: vi.fn((_url: string) => Promise.resolve(new Response('image data'))),
    },
}))

describe('protocol', () => {
    beforeEach(() => {
        vi.resetModules()
        vi.clearAllMocks()
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

    it('handler serves a cached thumbnail when thumbnail is requested', async () => {
        const { nativeImage, protocol, net } = await import('electron')
        const { registerAppProtocol } = await import('../protocol')
        const dir = await mkdtemp(path.join(tmpdir(), 'photorag-source-'))
        const filePath = path.join(dir, 'large photo.jpg')
        await writeFile(filePath, 'source image placeholder')

        registerAppProtocol()

        const handler = vi.mocked(protocol.handle).mock.calls[0][1]
        const request = new Request(
            `app://local-image?path=${encodeURIComponent(filePath)}&thumbnail=1&width=360&height=270`
        )

        await handler(request)

        expect(nativeImage.createThumbnailFromPath).toHaveBeenCalledWith(filePath, { width: 360, height: 270 })
        const fetchedUrl = vi.mocked(net.fetch).mock.calls[0][0]
        expect(fetchedUrl).toMatch(/^file:\/\/\/.*thumbnail-cache.*\.png$/)
        expect(fetchedUrl).not.toContain(encodeURIComponent('large photo.jpg'))
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
