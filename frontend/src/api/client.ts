import { getBaseUrl } from './base'
import type {
    Photo, PaginatedPhotos, Watcher, Job,
    SystemStatus, SearchResult, ChatResponse, FolderScanner,
    AIModelConfig, AIModelConfigUpdate
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

    year?: number
    month?: number
    day?: number

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

    if (params.year !== undefined) query.set('year', String(params.year))
    if (params.month !== undefined) query.set('month', String(params.month))
    if (params.day !== undefined) query.set('day', String(params.day))

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

export interface AvailableDate {
    year: number
    month: number
    day: number
}

export async function getAvailableDates(params: Omit<GetPhotosParams, 'skip' | 'limit' | 'sort_by' | 'sort_order' | 'is_doc' | 'year' | 'month' | 'day'> = {}): Promise<AvailableDate[]> {
    const query = new URLSearchParams()
    if (params.camera_id) query.set('camera_id', String(params.camera_id))
    if (params.geoposition_id) query.set('geoposition_id', String(params.geoposition_id))
    params.tag_ids?.forEach(id => query.append('tag_ids', String(id)))
    params.category_ids?.forEach(id => query.append('category_ids', String(id)))
    const qs = query.toString() ? `?${query}` : ''
    return apiFetch<AvailableDate[]>(`/api/photos/available-dates/${qs}`)
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

export interface AppSettings { [key: string]: string }

export async function getSettings(): Promise<AppSettings> {
    return apiFetch<AppSettings>('/api/settings/')
}

export async function updateSetting(key: string, value: string): Promise<void> {
    await apiFetch(`/api/settings/${key}`, {
        method: 'PUT',
        body: JSON.stringify({ value }),
    })
}

export async function undoLastAction(): Promise<{ status: string; detail: string }> {
    return apiFetch('/api/history/undo/', { method: 'POST' })
}

export async function getSystemStatus(): Promise<SystemStatus> {
    return apiFetch<SystemStatus>('/api/system/status/')
}

export async function getWatchers(): Promise<Watcher[]> {
    return apiFetch<Watcher[]>('/api/watchers/')
}

export async function addWatcher(path: string, destination_path: string): Promise<Watcher> {
    return apiFetch<Watcher>('/api/watchers/', {
        method: 'POST',
        body: JSON.stringify({ path, destination_path }),
    })
}

export async function deleteWatcher(id: number): Promise<Watcher> {
    return apiFetch<Watcher>(`/api/watchers/${id}`, { method: 'DELETE' })
}

export async function getFolderScanners(): Promise<FolderScanner[]> {
    return apiFetch<FolderScanner[]>('/api/folder_scanners/progress/')
}

export async function addFolderScanner(path: string): Promise<FolderScanner> {
    return apiFetch<FolderScanner>('/api/folder_scanners/', {
        method: 'POST',
        body: JSON.stringify({ path }),
    })
}

export async function deleteFolderScanner(id: number): Promise<FolderScanner> {
    return apiFetch<FolderScanner>(`/api/scanners/${id}`, { method: 'DELETE' })
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

export async function getModelConfigs(): Promise<AIModelConfig[]> {
    return apiFetch<AIModelConfig[]>('/api/models/')
}

export async function updateModelConfig(type: string, config: AIModelConfigUpdate): Promise<AIModelConfig> {
    return apiFetch<AIModelConfig>(`/api/models/${type}`, {
        method: 'PUT',
        body: JSON.stringify(config),
    })
}

export interface ExactDuplicateEntry {
    id: number
    file_path: string
}

export interface PerceptualDuplicateEntry {
    id: number
    file_path: string
    hash_distance: number
}

export interface DuplicateGroup<T> {
    original: { id: number; file_path: string }
    duplicates: T[]
}

export interface DuplicatesResponse {
    exact: DuplicateGroup<ExactDuplicateEntry>[]
    perceptual: DuplicateGroup<PerceptualDuplicateEntry>[]
}

export async function getDuplicates(): Promise<DuplicatesResponse> {
    return apiFetch<DuplicatesResponse>('/api/duplicates/')
}

export async function archivePhotos(ids: number[]): Promise<{ archived: number; skipped: number; zip_path: string }> {
    return apiFetch(`/api/photos/archive`, {
        method: 'POST',
        body: JSON.stringify({ photo_ids: ids }),
    })
}

export async function deleteDuplicateRecord(recordId: number): Promise<{ id: number }> {
    return apiFetch(`/api/duplicates/${recordId}`, { method: 'DELETE' })
}

export async function unmarkGarbage(photoId: number): Promise<{ photo_id: number; removed: boolean }> {
    return apiFetch(`/api/garbage/${photoId}/issues`, { method: 'DELETE' })
}

export interface GarbageSummary {
    counts: Record<string, number>
}

export async function getGarbageSummary(): Promise<GarbageSummary> {
    return apiFetch<GarbageSummary>('/api/garbage/')
}

export async function getGarbagePhotos(
    issueType: string,
    skip = 0,
    limit = 20,
): Promise<PaginatedPhotos> {
    const qs = `?skip=${skip}&limit=${limit}`
    return apiFetch<PaginatedPhotos>(`/api/garbage/${issueType}/photos/${qs}`)
}

