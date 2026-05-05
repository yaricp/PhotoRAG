import React, { useEffect, useMemo, useState } from 'react'
import {
    getPhotos,
    getCategories,
    getTags,
    getCameras,
    getGeopositions,
} from '@/api/client'

import { PhotoCard } from '@/components/photos/PhotoCard'
import { Spinner } from '@/components/ui/Spinner'
import { Button } from '@/components/ui/Button'
import type { PaginatedPhotos } from '@/types/api'
import './GalleryPage.css'

type Category = { id: number; name: string }
type Tag = { id: number; name: string }
type Camera = { id: number; make: string | null; model: string | null }
type Geo = { id: number; address: string | null }

type SortField = 'created_at' | 'captured_at' | 'file_created_at' | 'image_width'
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
    const [geos, setGeos] = useState<Geo[]>([])

    const [selectedCategories, setSelectedCategories] = useState<number[]>([])
    const [selectedTags, setSelectedTags] = useState<number[]>([])
    const [selectedCamera, setSelectedCamera] = useState<number | null>(null)
    const [selectedGeo, setSelectedGeo] = useState<number | null>(null)

    const [sortBy, setSortBy] = useState<SortField>('created_at')
    const [sortOrder, setSortOrder] = useState<SortOrder>('desc')

    // LOAD FILTERS
    useEffect(() => {
        getCategories().then(setCategories)
        getTags().then(setTags)
        getCameras().then(setCameras)
        getGeopositions().then(setGeos)
    }, [])

    // MAIN QUERY
    useEffect(() => {
        setLoading(true)

        getPhotos({
            skip: page * limit,
            limit,
            sort_by: sortBy,
            sort_order: sortOrder,
            category_ids: selectedCategories.length ? selectedCategories : undefined,
            tag_ids: selectedTags.length ? selectedTags : undefined,
            camera_id: selectedCamera ?? undefined,
            geoposition_id: selectedGeo ?? undefined,
        })
            .then(setData)
            .finally(() => setLoading(false))
    }, [
        page,
        limit,
        selectedCategories,
        selectedTags,
        selectedCamera,
        selectedGeo,
        sortBy,
        sortOrder,
    ])

    // TOGGLES
    const toggleTag = (id: number) => {
        setSelectedTags(prev =>
            prev.includes(id) ? prev.filter(t => t !== id) : [...prev, id]
        )
        setPage(0)
    }

    const toggleCategory = (id: number) => {
        setSelectedCategories(prev =>
            prev.includes(id) ? prev.filter(c => c !== id) : [...prev, id]
        )
        setPage(0)
    }

    const resetFilters = () => {
        setSelectedCategories([])
        setSelectedTags([])
        setSelectedCamera(null)
        setSelectedGeo(null)
        setSortBy('created_at')
        setSortOrder('desc')
        setPage(0)
    }

    const totalPages = useMemo(() => {
        if (!data?.total) return 1
        return Math.ceil(data.total / limit)
    }, [data, limit])

    return (
        <div className="gallery-layout">

            {/* MAIN GRID */}
            <div className="gallery-main">

                {loading && (
                    <div className="gallery-center">
                        <Spinner size="lg" />
                    </div>
                )}

                {!loading && data && (
                    <div className="gallery-grid">
                        {data.items.map(photo => (
                            <PhotoCard
                                key={`${photo.id}-${photo.hash}`}
                                photo={photo}
                            />
                        ))}
                    </div>
                )}

                {/* PAGINATION */}
                <div className="gallery-pagination">
                    <Button
                        disabled={page === 0}
                        onClick={() => setPage(p => Math.max(0, p - 1))}
                    >
                        Prev
                    </Button>

                    <span>
                        {page + 1} / {totalPages}
                    </span>

                    <Button
                        disabled={page + 1 >= totalPages}
                        onClick={() => setPage(p => p + 1)}
                    >
                        Next
                    </Button>
                </div>
            </div>

            {/* RIGHT SIDEBAR */}
            <aside className="gallery-sidebar">

                <Button onClick={resetFilters} size="sm">
                    Reset
                </Button>

                <div className="divider" />

                {/* LIMIT */}
                <div className="filter-block">
                    <label>Per page</label>
                    <select value={limit} onChange={(e) => {
                        setLimit(Number(e.target.value))
                        setPage(0)
                    }}>
                        {[10, 20, 50, 100].map(v => (
                            <option key={v} value={v}>{v}</option>
                        ))}
                    </select>
                </div>

                <div className="divider" />

                {/* SORT */}
                <div className="filter-block">
                    <label>Sort</label>

                    <select
                        value={sortBy}
                        onChange={(e) => {
                            setSortBy(e.target.value as SortField)
                            setPage(0)
                        }}
                    >
                        <option value="created_at">Created</option>
                        <option value="captured_at">Captured</option>
                        <option value="file_created_at">File</option>
                        <option value="image_width">Width</option>
                    </select>

                    <button
                        className="mini-btn"
                        onClick={() => {
                            setSortOrder(p => (p === 'asc' ? 'desc' : 'asc'))
                            setPage(0)
                        }}
                    >
                        {sortOrder}
                    </button>
                </div>

                <div className="divider" />

                {/* CATEGORIES */}
                <div className="filter-block">
                    <label>Categories</label>
                    <div className="chip-list">
                        {categories.map(c => (
                            <button
                                key={c.id}
                                className={selectedCategories.includes(c.id) ? 'chip active' : 'chip'}
                                onClick={() => toggleCategory(c.id)}
                            >
                                {c.name}
                            </button>
                        ))}
                    </div>
                </div>

                <div className="divider" />

                {/* CAMERAS */}
                <div className="filter-block">
                    <label>Cameras</label>
                    <div className="chip-list">
                        <button
                            className={!selectedCamera ? 'chip active' : 'chip'}
                            onClick={() => setSelectedCamera(null)}
                        >
                            All
                        </button>

                        {cameras.map(c => (
                            <button
                                key={c.id}
                                className={selectedCamera === c.id ? 'chip active' : 'chip'}
                                onClick={() => setSelectedCamera(c.id)}
                            >
                                {(c.make ?? '') + ' ' + (c.model ?? '')}
                            </button>
                        ))}
                    </div>
                </div>

                <div className="divider" />

                {/* GEO */}
                <div className="filter-block">
                    <label>Location</label>
                    <div className="chip-list">
                        <button
                            className={!selectedGeo ? 'chip active' : 'chip'}
                            onClick={() => setSelectedGeo(null)}
                        >
                            All
                        </button>

                        {geos.map(g => (
                            <button
                                key={g.id}
                                className={selectedGeo === g.id ? 'chip active' : 'chip'}
                                onClick={() => setSelectedGeo(g.id)}
                            >
                                {g.address?.slice(0, 20) ?? `Geo ${g.id}`}
                            </button>
                        ))}
                    </div>
                </div>

                <div className="divider" />

                {/* TAGS */}
                <div className="filter-block">
                    <label>Tags</label>
                    <div className="tag-cloud">
                        {tags.map(t => (
                            <button
                                key={t.id}
                                className={selectedTags.includes(t.id) ? 'tag active' : 'tag'}
                                onClick={() => toggleTag(t.id)}
                            >
                                {t.name}
                            </button>
                        ))}
                    </div>
                </div>

            </aside>
        </div>
    )
}