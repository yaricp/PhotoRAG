import React, { useEffect, useMemo, useState } from 'react'
import { getPhotos, getAvailableDates } from '@/api/client'
import type { AvailableDate } from '@/api/client'
import { PhotoCard } from '@/components/photos/PhotoCard'
import { Spinner } from '@/components/ui/Spinner'
import { Button } from '@/components/ui/Button'
import { FilterBar } from '@/components/ui/FilterBar'
import type { PaginatedPhotos } from '@/types/api'
import './GalleryPage.css'

type SortField = 'created_at' | 'captured_at' | 'file_created_at' | 'image_width'
type SortOrder = 'asc' | 'desc'

const DEFAULT_LIMIT = 20

export function GalleryPage() {
    const [data, setData] = useState<PaginatedPhotos | null>(null)
    const [loading, setLoading] = useState(true)

    const [page, setPage] = useState(0)
    const [limit, setLimit] = useState(DEFAULT_LIMIT)

    const [selectedCategories, setSelectedCategories] = useState<number[]>([])
    const [selectedTags, setSelectedTags] = useState<number[]>([])
    const [selectedCamera, setSelectedCamera] = useState<number | null>(null)
    const [selectedGeo, setSelectedGeo] = useState<number | null>(null)
    const [selectedYear, setSelectedYear] = useState<number | null>(null)
    const [selectedMonth, setSelectedMonth] = useState<number | null>(null)
    const [selectedDay, setSelectedDay] = useState<number | null>(null)

    const [sortBy, setSortBy] = useState<SortField>('created_at')
    const [sortOrder, setSortOrder] = useState<SortOrder>('desc')

    const [availableDates, setAvailableDates] = useState<AvailableDate[]>([])

    // Load available dates once on mount
    useEffect(() => {
        getAvailableDates().then(setAvailableDates)
    }, [])

    // Main query
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
            year: selectedYear ?? undefined,
            month: selectedMonth ?? undefined,
            day: selectedDay ?? undefined,
        })
            .then(setData)
            .finally(() => setLoading(false))
    }, [page, limit, selectedCategories, selectedTags, selectedCamera, selectedGeo, selectedYear, selectedMonth, selectedDay, sortBy, sortOrder])

    const toggleTag = (id: number) => {
        setSelectedTags(prev => prev.includes(id) ? prev.filter(t => t !== id) : [...prev, id])
        setPage(0)
    }

    const toggleCategory = (id: number) => {
        setSelectedCategories(prev => prev.includes(id) ? prev.filter(c => c !== id) : [...prev, id])
        setPage(0)
    }

    const handleDateSelect = (year?: number, month?: number, day?: number) => {
        setSelectedYear(year ?? null)
        setSelectedMonth(month ?? null)
        setSelectedDay(day ?? null)
        setPage(0)
    }

    const resetFilters = () => {
        setSelectedCategories([])
        setSelectedTags([])
        setSelectedCamera(null)
        setSelectedGeo(null)
        setSelectedYear(null)
        setSelectedMonth(null)
        setSelectedDay(null)
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
            <FilterBar
                selectedTags={selectedTags}
                selectedCategories={selectedCategories}
                selectedCamera={selectedCamera}
                selectedGeo={selectedGeo}
                selectedYear={selectedYear}
                selectedMonth={selectedMonth}
                selectedDay={selectedDay}
                availableDates={availableDates}
                sortBy={sortBy}
                sortOrder={sortOrder}
                limit={limit}
                onTagToggle={toggleTag}
                onCategoryToggle={toggleCategory}
                onCameraSelect={id => { setSelectedCamera(id); setPage(0) }}
                onGeoSelect={id => { setSelectedGeo(id); setPage(0) }}
                onDateSelect={handleDateSelect}
                onSortByChange={field => { setSortBy(field as SortField); setPage(0) }}
                onSortOrderToggle={() => { setSortOrder(p => p === 'asc' ? 'desc' : 'asc'); setPage(0) }}
                onLimitChange={val => { setLimit(val); setPage(0) }}
                onReset={resetFilters}
            />

            {loading && (
                <div className="gallery-center">
                    <Spinner size="lg" />
                </div>
            )}

            {!loading && data && (
                <div className="gallery-grid">
                    {data.items.map(photo => (
                        <PhotoCard
                            key={photo.id}
                            photo={photo}
                        />
                    ))}
                </div>
            )}

            <div className="gallery-pagination">
                <Button
                    disabled={page === 0}
                    onClick={() => setPage(p => Math.max(0, p - 1))}
                >
                    Prev
                </Button>

                <span>{page + 1} / {totalPages}</span>

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
