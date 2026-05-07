export interface Photo {
    id: number
    file_path: string
    description: string | null
    translated_description: string | null
    is_doc: boolean
    ocr_text: string | null
    created_at: string
    updated_at: string
    tags: PhotoTag[]
    categories: PhotoCategory[]
    camera: Camera | null
    geoposition: Geoposition | null
}

export interface PhotoTag {
    tag: Tag
    confidence_score: number
}

export interface PhotoCategory {
    category: Category
    confidence_score: number
}

export interface Tag {
    id: number
    name: string
}

export interface Category {
    id: number
    name: string
}

export interface Camera {
    id: number
    make: string | null
    model: string | null
}

export interface Geoposition {
    id: number
    latitude: number
    longitude: number
    altitude: number | null
}

export interface PaginatedPhotos {
    items: Photo[]
    total: number
    page: number
    size: number
    pages: number
}

export interface Watcher {
    id: number
    path: string
    status: string
    updated_at: string
    destination_path: string
}

export interface FolderScanner {
    id: number
    path: string
    progress: number
}


export interface Job {
    id: number
    photo_id: number
    phase: string
    tasks: string
    created_at: string
    updated_at: string
    file_path: string
}

export interface ModelStatus {
    name: string
    status: 'ready' | 'loading' | 'error'
    message: string | null
}

export interface SystemStatus {
    models: ModelStatus[]
}

export interface SearchResult {
    photo: Photo
    score: number
}

export interface ChatMessage {
    role: 'user' | 'assistant'
    content: string
}

export interface ChatResponse {
    message: string
    thread_id: string
    photos: Photo[]
}