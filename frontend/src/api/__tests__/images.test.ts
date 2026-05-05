import { describe, it, expect, beforeEach } from 'vitest'

describe('photoImageUrl', () => {
    beforeEach(() => {
        delete (window as any).electronAPI
    })

    it('returns app:// URL when electronAPI present', async () => {
        (window as any).electronAPI = { getBackendPort: async () => 8000 }
        const { photoImageUrl } = await import('../images')
        const url = photoImageUrl('/Users/test/Photos/img.png')
        expect(url).toMatch(/^app:\/\/local-image/)
    })

    it('encodes the file path in app:// URL', async () => {
        (window as any).electronAPI = { getBackendPort: async () => 8000 }
        const { photoImageUrl } = await import('../images')
        const url = photoImageUrl('/Users/test/My Photos/img.png')
        expect(url).toContain(encodeURIComponent('/Users/test/My Photos/img.png'))
    })

    it('returns /api/static URL when in browser', async () => {
        const { photoImageUrl } = await import('../images')
        const url = photoImageUrl('/Users/test/Photos/img.png')
        expect(url).toMatch(/^\/api\/static/)
    })

    it('path is URL-encoded in browser mode too', async () => {
        const { photoImageUrl } = await import('../images')
        const url = photoImageUrl('/Users/test/My Photos/img.png')
        expect(url).toContain(encodeURIComponent('/Users/test/My Photos/img.png'))
    })
})