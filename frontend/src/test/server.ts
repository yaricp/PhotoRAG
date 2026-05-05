import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import {
    makePhoto, makePaginatedPhotos, makeWatcher,
    makeJob, makeSystemStatus, makeChatResponse,
    makeTag, makeCategory, makeCamera, makeGeoposition
} from './factories'

const BASE = 'http://localhost:8000'

const photo1 = makePhoto({ id: 1, file_path: '/photos/img1.png' })
const photo2 = makePhoto({ id: 2, file_path: '/photos/img2.png', is_doc: true })
const photo3 = makePhoto({ id: 3, file_path: '/photos/img3.png' })

export const handlers = [
    http.get(`${BASE}/api/photos/`, () =>
        HttpResponse.json(makePaginatedPhotos([photo1, photo2, photo3]))
    ),

    http.get(`${BASE}/api/photos/:id`, ({ params }) =>
        HttpResponse.json(makePhoto({ id: Number(params.id) }))
    ),

    http.delete(`${BASE}/api/photos/:id`, ({ params }) =>
        HttpResponse.json(makePhoto({ id: Number(params.id) }))
    ),

    http.post(`${BASE}/api/search/`, () =>
        HttpResponse.json([{ photo: photo1, score: 0.95 }])
    ),

    http.post(`${BASE}/api/chat/`, () =>
        HttpResponse.json(makeChatResponse())
    ),

    http.get(`${BASE}/api/system/status/`, () =>
        HttpResponse.json(makeSystemStatus())
    ),

    http.get(`${BASE}/api/watchers/`, () =>
        HttpResponse.json([makeWatcher()])
    ),

    http.post(`${BASE}/api/watch/`, () =>
        HttpResponse.json(makeWatcher())
    ),

    http.delete(`${BASE}/api/watchers/:id`, () =>
        new HttpResponse(null, { status: 204 })
    ),

    http.get(`${BASE}/api/tags/`, () =>
        HttpResponse.json([makeTag(), makeTag({ id: 2, name: 'invoice' })])
    ),

    http.get(`${BASE}/api/categories/`, () =>
        HttpResponse.json([makeCategory(), makeCategory({ id: 2, name: 'personal' })])
    ),

    http.get(`${BASE}/api/cameras/`, () =>
        HttpResponse.json([makeCamera()])
    ),

    http.get(`${BASE}/api/geopositions/`, () =>
        HttpResponse.json([makeGeoposition()])
    ),

    http.get(`${BASE}/api/job/:photoId`, ({ params }) =>
        HttpResponse.json(makeJob({ photo_id: Number(params.photoId) }))
    ),

    http.get(`${BASE}/api/stream/`, () =>
        new HttpResponse(null, { status: 200 })
    ),
]

export const server = setupServer(...handlers)