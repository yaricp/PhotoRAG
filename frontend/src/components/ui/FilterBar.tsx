import React from 'react'
import { TagsFilterButton } from './TagsFilterButton'
import { CategoriesFilterButton } from './CategoriesFilterButton'
import { CamerasFilterButton } from './CamerasFilterButton'
import { GeopositionsFilterButton } from './GeopositionsFilterButton'
import { DateFilterButton } from './DateFilterButton'
import { Button } from './Button'
import type { AvailableDate } from '@/api/client'

export interface FilterBarProps {
    selectedTags: number[]
    selectedCategories: number[]
    selectedCamera: number | null
    selectedGeo: number | null
    selectedYear: number | null
    selectedMonth: number | null
    selectedDay: number | null
    availableDates: AvailableDate[]

    sortBy: string
    sortOrder: 'asc' | 'desc'
    limit: number

    onTagToggle: (id: number) => void
    onCategoryToggle: (id: number) => void
    onCameraSelect: (id: number | null) => void
    onGeoSelect: (id: number | null) => void
    onDateSelect: (year?: number, month?: number, day?: number) => void
    onSortByChange: (field: string) => void
    onSortOrderToggle: () => void
    onLimitChange: (limit: number) => void
    onReset: () => void
}

export function FilterBar({
    selectedTags, selectedCategories, selectedCamera, selectedGeo,
    selectedYear, selectedMonth, selectedDay, availableDates,
    sortBy, sortOrder, limit,
    onTagToggle, onCategoryToggle, onCameraSelect, onGeoSelect, onDateSelect,
    onSortByChange, onSortOrderToggle, onLimitChange, onReset,
}: FilterBarProps) {
    return (
        <div className="filter-bar">
            <div className="filter-bar__filters">
                <TagsFilterButton selectedTags={selectedTags} onToggle={onTagToggle} />
                <CategoriesFilterButton selectedCategories={selectedCategories} onToggle={onCategoryToggle} />
                <CamerasFilterButton selectedCamera={selectedCamera} onSelect={onCameraSelect} />
                <GeopositionsFilterButton selectedGeo={selectedGeo} onSelect={onGeoSelect} />
                <DateFilterButton
                    selectedYear={selectedYear}
                    selectedMonth={selectedMonth}
                    selectedDay={selectedDay}
                    availableDates={availableDates}
                    onSelect={onDateSelect}
                />
            </div>

            <div className="filter-bar__controls">
                <select
                    className="filter-bar__select"
                    value={sortBy}
                    onChange={e => onSortByChange(e.target.value)}
                >
                    <option value="created_at">Created</option>
                    <option value="captured_at">Captured</option>
                    <option value="file_created_at">File</option>
                    <option value="image_width">Width</option>
                </select>

                <button className="filter-bar__sort-order" onClick={onSortOrderToggle}>
                    {sortOrder === 'desc' ? '↓' : '↑'}
                </button>

                <select
                    className="filter-bar__select"
                    value={limit}
                    onChange={e => onLimitChange(Number(e.target.value))}
                >
                    {[5, 10, 20, 50, 100].map(v => (
                        <option key={v} value={v}>{v} / page</option>
                    ))}
                </select>

                <Button size="sm" variant="ghost" onClick={onReset}>
                    Reset
                </Button>
            </div>
        </div>
    )
}
