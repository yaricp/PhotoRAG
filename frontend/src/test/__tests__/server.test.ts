import { describe, it, expect } from 'vitest'
import { server } from '../server'

const BASE = 'http://localhost:8000'

describe('MSW handlers', () => {
    it('GET /api/photos/ returns paginated photos', async () => {
        const res = await fetch(`${BASE}/api/photos/`)
        const data = await res.json()
        expect(res.status).toBe(200)
        expect(data.items).toHaveLength(3)
        expect(data.total).toBe(3)
    })

    it('GET /api/photos/:id returns single photo', async () => {
        const res = await fetch(`${BASE}/api/photos/5`)
        const data = await res.json()
        expect(res.status).toBe(200)
        expect(data.id).toBe(5)
    })

    it('DELETE /api/photos/:id returns deleted photo', async () => {
        const res = await fetch(`${BASE}/api/photos/1`, { method: 'DELETE' })
        expect(res.status).toBe(200)
    })

    it('POST /api/search/ returns results with score', async () => {
        const res = await fetch(`${BASE}/api/search/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: 'invoice', k: 10 })
        })
        const data = await res.json()
        expect(res.status).toBe(200)
        expect(data[0].score).toBeGreaterThan(0)
    })

    it('POST /api/chat/ returns message and thread_id', async () => {
        const res = await fetch(`${BASE}/api/chat/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: 'show documents' })
        })
        const data = await res.json()
        expect(res.status).toBe(200)
        expect(data.thread_id).toBeTruthy()
        expect(data.message).toBeTruthy()
    })

    it('GET /api/system/status/ returns model statuses', async () => {
        const res = await fetch(`${BASE}/api/system/status/`)
        const data = await res.json()
        expect(res.status).toBe(200)
        expect(data.models).toHaveLength(3)
    })

    it('GET /api/watchers/ returns list', async () => {
        const res = await fetch(`${BASE}/api/watchers/`)
        const data = await res.json()
        expect(Array.isArray(data)).toBe(true)
    })

    it('POST /api/watch/ creates watcher', async () => {
        const res = await fetch(`${BASE}/api/watch/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: '/Users/test/NewPhotos' })
        })
        expect(res.status).toBe(200)
    })

    it('GET /api/tags/ returns tags array', async () => {
        const res = await fetch(`${BASE}/api/tags/`)
        const data = await res.json()
        expect(Array.isArray(data)).toBe(true)
        expect(data[0].name).toBeTruthy()
    })

    it('GET /api/job/:photoId returns job', async () => {
        const res = await fetch(`${BASE}/api/job/42`)
        const data = await res.json()
        expect(data.photo_id).toBe(42)
        expect(data.status).toBe('processing')
    })

    it('GET /api/cameras/ returns cameras', async () => {
        const res = await fetch(`${BASE}/api/cameras/`)
        const data = await res.json()
        expect(Array.isArray(data)).toBe(true)
    })

    it('GET /api/geopositions/ returns geopositions', async () => {
        const res = await fetch(`${BASE}/api/geopositions/`)
        const data = await res.json()
        expect(Array.isArray(data)).toBe(true)
    })
})