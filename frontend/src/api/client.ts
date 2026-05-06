import { getBaseUrl } from './base'
import type {
    Photo, PaginatedPhotos, Watcher, Job,
    SystemStatus, SearchResult, ChatResponse
} from '@/types/api'

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
    const base = await getBaseUrl()
    const res = await fetch(`${base}${path}`, {
        headers: { 'Content-Type': 'application/json', ...init?.headers },
        ...init,
    })
    if (!res.ok) throw new Error(`API error ${res.status}: ${path}`)
    return res.json() as Promise<T>
}

export interface GetPhotosParams {
    skip?: number
    limit?: number
    is_doc?: boolean

    tag_ids?: number[]
    category_ids?: number[]
    camera_id?: number
    geoposition_id?: number

    sort_by?: string
    sort_order?: 'asc' | 'desc'
}

export async function getPhotos(params: GetPhotosParams = {}): Promise<PaginatedPhotos> {
    const query = new URLSearchParams()

    if (params.skip !== undefined) query.set('skip', String(params.skip))
    if (params.limit !== undefined) query.set('limit', String(params.limit))
    if (params.is_doc !== undefined) query.set('is_doc', String(params.is_doc))

    if (params.sort_by) query.set('sort_by', params.sort_by)
    if (params.sort_order) query.set('sort_order', params.sort_order)

    if (params.camera_id) query.set('camera_id', String(params.camera_id))
    if (params.geoposition_id) query.set('geoposition_id', String(params.geoposition_id))

    console.log("query1", query)
    // ✅ MULTI TAGS (ВАЖНО)
    params.tag_ids?.forEach(id => {
        query.append('tag_ids', String(id))
    })
    console.log("query2", query)
    // ✅ MULTI CATEGORIES
    params.category_ids?.forEach(id => {
        query.append('category_ids', String(id))
    })
    console.log("query3", query)
    const qs = query.toString() ? `?${query}` : ''
    console.log(qs)
    return apiFetch<PaginatedPhotos>(`/api/photos/${qs}`)
}

export async function getPhoto(id: number): Promise<Photo> {
    return apiFetch<Photo>(`/api/photos/${id}`)
}

export async function deletePhoto(id: number): Promise<Photo> {
    return apiFetch<Photo>(`/api/photos/${id}`, { method: 'DELETE' })
}

export interface SearchParams {
    query: string
    k?: number
    threshold?: number
}

export async function searchPhotos(params: SearchParams): Promise<Photo[]> {
    return apiFetch<Photo[]>('/api/search/', {
        method: 'POST',
        body: JSON.stringify(params),
    })
}

export interface ChatParams {
    message: string
    thread_id?: string
}

export async function sendChat(params: ChatParams): Promise<ChatResponse> {
    return apiFetch<ChatResponse>('/api/chat/', {
        method: 'POST',
        body: JSON.stringify(params),
    })
}

export async function getSystemStatus(): Promise<SystemStatus> {
    return apiFetch<SystemStatus>('/api/system/status/')
}

export async function getWatchers(): Promise<Watcher[]> {
    return apiFetch<Watcher[]>('/api/watchers/')
}

export async function addWatcher(path: string): Promise<Watcher> {
    return apiFetch<Watcher>('/api/watchers/', {
        method: 'POST',
        body: JSON.stringify({ path }),
    })
}

export async function deleteWatcher(id: number): Promise<Watcher> {
    return apiFetch<Watcher>(`/api/watchers/${id}`, { method: 'DELETE' })
}

export async function getJob(photoId: number): Promise<Job> {
    return apiFetch<Job>(`/api/jobs/${photoId}`)
}

export async function getJobs(): Promise<Job[]> {
    return apiFetch<Job[]>(`/api/jobs/`)
}

export async function getTags() {
    return apiFetch<{ id: number; name: string }[]>('/api/tags/')
}

export async function getCategories() {
    return apiFetch<{ id: number; name: string }[]>('/api/categories/')
}

export async function getCameras() {
    return apiFetch<{ id: number; make: string | null; model: string | null }[]>('/api/cameras/')
}

export async function getGeopositions() {
    return apiFetch<{ id: number; address: string | null; latitude: number; longitude: number }[]>('/api/geopositions/')
}