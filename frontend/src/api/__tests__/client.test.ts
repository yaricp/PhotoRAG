import { describe, it, expect, beforeAll, afterAll, afterEach, vi } from 'vitest'
import { server } from '@/test/server'
import { http, HttpResponse } from 'msw'

vi.mock('../base', () => ({
    getBaseUrl: async () => 'http://localhost:8000'
}))

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

describe('api client', () => {
    describe('photos', () => {
        it('getPhotos returns paginated result', async () => {
            const { getPhotos } = await import('../client')
            const result = await getPhotos()
            expect(result.items).toHaveLength(3)
            expect(result.total).toBe(3)
        })

        it('getPhotos passes query params', async () => {
            let capturedUrl = ''
            server.use(
                http.get('http://localhost:8000/api/photos/', ({ request }) => {
                    capturedUrl = request.url
                    return HttpResponse.json({ items: [], total: 0, page: 1, size: 20, pages: 0 })
                })
            )
            const { getPhotos } = await import('../client')
            await getPhotos({ page: 2, is_doc: true })
            expect(capturedUrl).toContain('page=2')
            expect(capturedUrl).toContain('is_doc=true')
        })

        it('getPhoto returns single photo', async () => {
            const { getPhoto } = await import('../client')
            const photo = await getPhoto(7)
            expect(photo.id).toBe(7)
        })

        it('deletePhoto calls DELETE endpoint', async () => {
            let method = ''
            server.use(
                http.delete('http://localhost:8000/api/photos/:id', ({ request }) => {
                    method = request.method
                    return HttpResponse.json({})
                })
            )
            const { deletePhoto } = await import('../client')
            await deletePhoto(1)
            expect(method).toBe('DELETE')
        })
    })

    describe('search', () => {
        it('searchPhotos posts query and returns results', async () => {
            let body: any = null
            server.use(
                http.post('http://localhost:8000/api/search/', async ({ request }) => {
                    body = await request.json()
                    return HttpResponse.json([])
                })
            )
            const { searchPhotos } = await import('../client')
            await searchPhotos({ query: 'invoice', k: 5 })
            expect(body.query).toBe('invoice')
            expect(body.k).toBe(5)
        })
    })

    describe('chat', () => {
        it('sendChat posts message and returns response', async () => {
            const { sendChat } = await import('../client')
            const res = await sendChat({ message: 'show docs' })
            expect(res.thread_id).toBeTruthy()
            expect(res.message).toBeTruthy()
        })
    })

    describe('system', () => {
        it('getSystemStatus returns model statuses', async () => {
            const { getSystemStatus } = await import('../client')
            const status = await getSystemStatus()
            expect(status.models).toHaveLength(3)
        })
    })

    describe('watchers', () => {
        it('getWatchers returns list', async () => {
            const { getWatchers } = await import('../client')
            const watchers = await getWatchers()
            expect(Array.isArray(watchers)).toBe(true)
        })

        it('addWatcher posts path', async () => {
            let body: any = null
            server.use(
                http.post('http://localhost:8000/api/watch/', async ({ request }) => {
                    body = await request.json()
                    return HttpResponse.json({})
                })
            )
            const { addWatcher } = await import('../client')
            await addWatcher('/Users/test/NewPhotos')
            expect(body.path).toBe('/Users/test/NewPhotos')
        })
    })

    describe('job', () => {
        it('getJob returns job for photoId', async () => {
            const { getJob } = await import('../client')
            const job = await getJob(42)
            expect(job.photo_id).toBe(42)
        })
    })
})