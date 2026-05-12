import type {
    Photo, PhotoTag, PhotoCategory, Tag, Category,
    Camera, Geoposition, Watcher, Job, ModelStatus,
    SystemStatus, ChatResponse, PaginatedPhotos
} from '@/types/api'

export const makeTag = (overrides?: Partial<Tag>): Tag => ({
    id: 1,
    name: 'document',
    ...overrides
})

export const makeCategory = (overrides?: Partial<Category>): Category => ({
    id: 1,
    name: 'work',
    ...overrides
})

export const makeCamera = (overrides?: Partial<Camera>): Camera => ({
    id: 1,
    make: 'Apple',
    model: 'iPhone 15 Pro',
    ...overrides
})

export const makeGeoposition = (overrides?: Partial<Geoposition>): Geoposition => ({
    id: 1,
    latitude: 41.6938,
    longitude: 44.8015,
    altitude: null,
    ...overrides
})

export const makePhotoTag = (overrides?: Partial<PhotoTag>): PhotoTag => ({
    tag: makeTag(),
    confidence_score: 0.9,
    ...overrides
})

export const makePhotoCategory = (overrides?: Partial<PhotoCategory>): PhotoCategory => ({
    category: makeCategory(),
    confidence_score: 0.85,
    ...overrides
})

export const makePhoto = (overrides?: Partial<Photo>): Photo => ({
    id: 1,
    file_path: '/Users/test/Photos/doc1.png',
    description: 'A formal document with text',
    is_doc: false,
    is_trash: false,
    ocr_text: null,
    created_at: '2024-01-01T00:00:00Z',
    captured_at: null,
    file_created_at: null,
    image_width: null,
    image_height: null,
    iso: null,
    aperture: null,
    focal_length: null,
    shutter_speed: null,
    offset_time: null,
    tags_rel: [makePhotoTag()],
    categories_rel: [makePhotoCategory()],
    camera: makeCamera(),
    geoposition: null,
    ...overrides
})

export const makePaginatedPhotos = (
    items: Photo[] = [makePhoto()],
    overrides?: Partial<PaginatedPhotos>
): PaginatedPhotos => ({
    items,
    total: items.length,
    page: 1,
    size: 20,
    pages: 1,
    ...overrides
})

export const makeWatcher = (overrides?: Partial<Watcher>): Watcher => ({
    id: 1,
    path: '/Users/test/Photos',
    is_active: true,
    created_at: '2024-01-01T00:00:00Z',
    ...overrides
})

export const makeJob = (overrides?: Partial<Job>): Job => ({
    id: 1,
    photo_id: 1,
    status: 'processing',
    created_at: '2024-01-01T00:00:00Z',
    ...overrides
})

export const makeModelStatus = (overrides?: Partial<ModelStatus>): ModelStatus => ({
    name: 'clip',
    status: 'ready',
    message: null,
    ...overrides
})

export const makeSystemStatus = (overrides?: Partial<SystemStatus>): SystemStatus => ({
    models: [
        makeModelStatus({ name: 'clip' }),
        makeModelStatus({ name: 'easyocr' }),
        makeModelStatus({ name: 'llava' }),
    ],
    ...overrides
})

export const makeChatResponse = (overrides?: Partial<ChatResponse>): ChatResponse => ({
    message: 'Here are some matching photos.',
    thread_id: 'thread-abc-123',
    photos: [makePhoto()],
    ...overrides
})