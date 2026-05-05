import React, { useEffect, useMemo, useState } from 'react'
import { getPhotos, getCategories, getTags, getCameras, getGeopositions } from '@/api/client'
import { PhotoCard } from '@/components/photos/PhotoCard'
import { Spinner } from '@/components/ui/Spinner'
import { Button } from '@/components/ui/Button'
import type { PaginatedPhotos } from '@/types/api'
import './GalleryPage.css'

type Category = { id: number; name: string }
type Tag = { id: number; name: string }
type Camera = { id: number; make: string | null; model: string | null }
type Geoposition = {
    id: number
    address: string | null
    latitude: number
    longitude: number
}

type SortField = 'created_at' | 'captured_at' | 'image_width'
type SortOrder = 'asc' | 'desc'

const DEFAULT_LIMIT = 20

export function GalleryPage() {
    const [data, setData] = useState<PaginatedPhotos | null>(null)
    const [loading, setLoading] = useState(true)

    const [page, setPage] = useState(0)
    const [limit, setLimit] = useState(DEFAULT_LIMIT)

    const [categories, setCategories] = useState<Category[]>([])
    const [tags, setTags] = useState<Tag[]>([])
    const [cameras, setCameras] = useState<Camera[]>([])

    const [selectedCategories, setSelectedCategories] = useState<number[]>([])
    const [selectedTags, setSelectedTags] = useState<number[]>([])
    const [selectedCamera, setSelectedCamera] = useState<number | null>(null)

    const [sortBy, setSortBy] = useState<SortField>('created_at')
    const [sortOrder, setSortOrder] = useState<SortOrder>('desc')

    const [geopositions, setGeopositions] = useState<Geoposition[]>([])
    const [selectedGeoposition, setSelectedGeoposition] = useState<number | null>(null)

    useEffect(() => {
        getCategories().then(setCategories)
        getTags().then(setTags)
        getCameras().then(setCameras)
        getGeopositions().then(setGeopositions)
    }, [])

    useEffect(() => {
        setLoading(true)

        getPhotos({
            skip: page * limit,
            limit: limit,
            sort_by: sortBy,
            sort_order: sortOrder,
            category_ids: selectedCategories.length ? selectedCategories : undefined,
            tag_ids: selectedTags.length ? selectedTags : undefined,
            camera_id: selectedCamera ?? undefined,
            geoposition_id: selectedGeoposition ?? undefined,
        })
            .then(setData)
            .finally(() => setLoading(false))
    }, [page, limit, selectedCategories, selectedTags, selectedCamera, sortBy, sortOrder])

    const toggleTag = (id: number) => {
        setSelectedTags(prev =>
            prev.includes(id)
                ? prev.filter(t => t !== id)
                : [...prev, id]
        )
        setPage(0)
    }

    useEffect(() => {
        fetch('/api/geopositions')
            .then(r => r.json())
            .then(setGeopositions)
    }, [])

    const toggleCategories = (id: number) => {
        setSelectedCategories(prev =>
            prev.includes(id)
                ? prev.filter(t => t !== id)
                : [...prev, id]
        )
        setPage(0)
    }

    const resetFilters = () => {
        setSelectedCategories([])
        setSelectedTags([])
        setSelectedCamera(null)
        setSortBy('created_at')
        setSortOrder('desc')
        setPage(0)
    }

    const totalPages = useMemo(() => {
        if (!data?.total) return 1
        return Math.ceil(data.total / limit)
    }, [data, limit])

    const toggleSortOrder = () => {
        setSortOrder(prev => (prev === 'asc' ? 'desc' : 'asc'))
        setPage(0)
    }

    return (
        <div className="gallery-page">

            {/* TOOLBAR */}
            <div className="gallery-page__toolbar">

                <Button onClick={resetFilters}>
                    Reset filters
                </Button>

                {/* PAGE SIZE */}
                <div className="gallery-page__page-size">
                    <span>Per page:</span>
                    <select
                        value={limit}
                        onChange={(e) => {
                            setLimit(Number(e.target.value))
                            setPage(0)
                        }}
                    >
                        <option value={5}>5</option>
                        <option value={10}>10</option>
                        <option value={20}>20</option>
                        <option value={50}>50</option>
                    </select>
                </div>

                {/* SORT */}
                <div className="gallery-page__sort">
                    <select
                        value={sortBy}
                        onChange={(e) => {
                            setSortBy(e.target.value as SortField)
                            setPage(0)
                        }}
                    >
                        <option value="created_at">Created</option>
                        <option value="captured_at">Captured</option>
                        <option value="file_created_at">File created</option>
                        <option value="id">ID</option>
                    </select>

                    <Button onClick={toggleSortOrder}>
                        {sortOrder === 'asc' ? 'Asc' : 'Desc'}
                    </Button>
                </div>
            </div>

            {/* CATEGORY FILTER */}
            <div className="gallery-page__categories">
                {categories.map(cat => {
                    const active = selectedCategories.includes(cat.id)

                    return (
                        <button
                            key={cat.id}
                            className={active ? 'category-chip category-chip--active' : 'category-chip'}
                            onClick={() => toggleCategories(cat.id)}
                        >
                            {cat.name}
                        </button>
                    )
                })}
            </div>

            {/* CAMERA FILTER */}
            <div className="gallery-page__categories">
                <button
                    className={!selectedCamera ? 'category-chip category-chip--active' : 'category-chip'}
                    onClick={() => {
                        setSelectedCamera(null)
                        setPage(0)
                    }}
                >
                    All cameras
                </button>

                {cameras.map(cam => {
                    const label = `${cam.make ?? ''} ${cam.model ?? ''}`.trim()
                    const active = selectedCamera === cam.id

                    return (
                        <button
                            key={cam.id}
                            className={active ? 'category-chip category-chip--active' : 'category-chip'}
                            onClick={() => {
                                setSelectedCamera(cam.id)
                                setPage(0)
                            }}
                        >
                            {label || `Camera ${cam.id}`}
                        </button>
                    )
                })}
            </div>

            {/* GEO FILTER */}
            <div className="gallery-page__categories">
                <button
                    className={!selectedGeoposition
                        ? 'category-chip category-chip--active'
                        : 'category-chip'
                    }
                    onClick={() => {
                        setSelectedGeoposition(null)
                        setPage(0)
                    }}
                >
                    All locations
                </button>

                {geopositions.map(pos => {
                    const active = selectedGeoposition === pos.id

                    return (
                        <button
                            key={pos.id}
                            className={
                                active
                                    ? 'category-chip category-chip--active'
                                    : 'category-chip'
                            }
                            onClick={() => {
                                setSelectedGeoposition(pos.id)
                                setPage(0)
                            }}
                        >
                            {pos.address
                                ? pos.address.slice(0, 30) + '...'
                                : `Location ${pos.id}`}
                        </button>
                    )
                })}
            </div>

            {/* TAG CLOUD */}
            <div className="gallery-page__tag-cloud">
                {tags.map(tag => {
                    const active = selectedTags.includes(tag.id)

                    return (
                        <button
                            key={tag.id}
                            onClick={() => toggleTag(tag.id)}
                            className={active ? 'tag tag--active' : 'tag'}
                        >
                            {tag.name}
                        </button>
                    )
                })}
            </div>

            {/* LOADING */}
            {loading && (
                <div className="gallery-page__center">
                    <Spinner size="lg" />
                </div>
            )}

            {/* GRID */}
            {!loading && data && (
                <div className="gallery-page__grid">
                    {data.items.map(photo => (
                        <PhotoCard key={`${photo.id}-${photo.hash}`} photo={photo} />
                    ))}
                </div>
            )}

            {/* PAGINATION */}
            <div className="gallery-page__pagination">
                <Button
                    disabled={page === 0}
                    onClick={() => setPage(p => Math.max(0, p - 1))}
                >
                    Prev
                </Button>

                <span>
                    Page {page + 1} / {totalPages}
                </span>

                <Button
                    disabled={page + 1 >= totalPages}
                    onClick={() => setPage(p => p + 1)}
                >
                    Next
                </Button>
            </div>
        </div>
    )
}