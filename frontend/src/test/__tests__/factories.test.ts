import { describe, it, expect } from 'vitest'
import {
    makePhoto, makePaginatedPhotos, makeWatcher,
    makeJob, makeSystemStatus, makeChatResponse,
    makeTag, makeCategory, makeCamera, makeGeoposition,
    makePhotoTag, makePhotoCategory
} from '../factories'

describe('factories', () => {
    it('makePhoto returns valid photo', () => {
        const photo = makePhoto()
        expect(photo.id).toBe(1)
        expect(photo.file_path).toBe('/Users/test/Photos/doc1.png')
        expect(photo.is_doc).toBe(false)
        expect(photo.tags_rel).toHaveLength(1)
    })

    it('makePhoto accepts overrides', () => {
        const photo = makePhoto({ id: 42, is_doc: true, ocr_text: 'hello' })
        expect(photo.id).toBe(42)
        expect(photo.is_doc).toBe(true)
        expect(photo.ocr_text).toBe('hello')
    })

    it('makePaginatedPhotos wraps items correctly', () => {
        const photos = [makePhoto({ id: 1 }), makePhoto({ id: 2 })]
        const result = makePaginatedPhotos(photos)
        expect(result.items).toHaveLength(2)
        expect(result.total).toBe(2)
        expect(result.pages).toBe(1)
    })

    it('makeWatcher returns active watcher', () => {
        const w = makeWatcher()
        expect(w.status).toBe('active')
        expect(w.path).toBe('/Users/test/Photos')
    })

    it('makeJob defaults to processing status', () => {
        const job = makeJob()
        expect(job.phase).toBe('processing')
    })

    it('makeSystemStatus has 3 models all ready', () => {
        const status = makeSystemStatus()
        expect(status.models).toHaveLength(3)
        status.models.forEach(m => expect(m.status).toBe('ready'))
    })

    it('makeChatResponse has thread_id and photos', () => {
        const res = makeChatResponse()
        expect(res.thread_id).toBeTruthy()
        expect(res.photos).toHaveLength(1)
    })

    it('makePhotoTag has confidence score between 0 and 1', () => {
        const pt = makePhotoTag()
        expect(pt.confidence_score).toBeGreaterThan(0)
        expect(pt.confidence_score).toBeLessThanOrEqual(1)
    })
})