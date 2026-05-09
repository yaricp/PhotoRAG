# REVISED Implementation Plan: Unified Modal-Based Filtering

> **Phase:** 7.2  
> **Feature:** Complete UI refactor for all filters + date filtering  
> **Approach:** Unified modal interface for all 6 filter dimensions  
> **Status:** In Planning

---

## Current State vs. Target State

### Current Implementation
- **Filters displayed in:** Right sidebar (always visible)
- **Filter types:** Tags, Categories, Cameras, Geopositions
- **Interaction:** Click buttons directly on sidebar
- **Limitation:** Takes up screen space, all filters visible at once

### Target State (After Implementation)
- **Filters displayed in:** Filter bar with buttons, modals on click
- **Filter types:** Tags, Categories, Cameras, Geopositions, **Date (NEW)**
- **Interaction:** 
  1. User sees 6 filter buttons in a horizontal bar
  2. Click button → modal opens
  3. Select filter value → modal closes + filter applies
  4. For dates: cascade through Year → Month → Day modals
- **Benefit:** Clean UI, less clutter, intuitive discovery

---

## UI Architecture

### Before (Current)
```
┌─────────────────────────────────────────────────┐
│                   Gallery Grid                  │
│                                                 │
│  ┌────────┐  ┌────────┐  ┌────────┐            │
│  │ Photo  │  │ Photo  │  │ Photo  │            │
│  └────────┘  └────────┘  └────────┘            │
│                                                 │
└─────────────────────────────────────────────────┘
                        │
                        ├─→ [Prev] [1/10] [Next]
                        │
                        └─→ Right Sidebar (always visible)
                            • Reset button
                            • Per page dropdown
                            • Sort options
                            • Categories (all chips visible)
                            • Tags (all chips visible)
                            • Cameras (all chips visible)
                            • Locations (all chips visible)
```

### After (Target)
```
┌───────────────────────────────────────────────────┐
│ [Tags] [Categories] [Cameras] [Locations] [Date] │  ← Filter Bar
├───────────────────────────────────────────────────┤
│                   Gallery Grid                    │
│                                                   │
│  ┌────────┐  ┌────────┐  ┌────────┐             │
│  │ Photo  │  │ Photo  │  │ Photo  │             │
│  └────────┘  └────────┘  └────────┘             │
│                                                   │
└───────────────────────────────────────────────────┘
         │
         ├─→ [Prev] [1/10] [Next]
         │
         └─→ Modal Layer (on filter button click)
             ┌──────────────────────┐
             │ Modal Backdrop       │
             │ ┌────────────────┐   │
             │ │ [Tag 1] [Tag2] │   │
             │ │ [Tag 3] [Tag4] │   │
             │ │ [Tag 5] ...    │   │
             │ └────────────────┘   │
             └──────────────────────┘
```

---

## Implementation Tasks

### PART 1: Backend (No Changes Needed for Existing Filters)

Backend already supports all filters. We only need to add date filtering:

#### Task 1.1: Add Date Filter to `get_all_photos()`
**File:** `backend/src/db_service.py`

```python
def get_all_photos(
    db: Session,
    skip: int = 0,
    limit: int = 50,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    category_ids: Optional[list[int]] = None,
    tag_ids: Optional[list[int]] = None,
    camera_id: Optional[int] = None,
    geoposition_id: Optional[int] = None,
    year: Optional[int] = None,          # NEW
    month: Optional[int] = None,          # NEW
    day: Optional[int] = None,            # NEW
) -> tuple[list[Photo], int]:
    # ... existing filters ...
    
    if year:
        query = query.filter(extract('year', Photo.captured_at) == year)
    if month:
        query = query.filter(extract('month', Photo.captured_at) == month)
    if day:
        query = query.filter(extract('day', Photo.captured_at) == day)
    
    return photos, total
```

#### Task 1.2: Add Available Dates Endpoint
**File:** `backend/src/main.py`

```python
@app.get("/api/photos/available-dates/")
def get_available_dates_endpoint(
    db: Session = Depends(get_db),
    category_ids: Optional[list[int]] = Query(None),
    tag_ids: Optional[list[int]] = Query(None),
    camera_id: Optional[int] = Query(None),
    geoposition_id: Optional[int] = Query(None),
) -> List[Dict[str, int]]:
    """Get all unique (year, month, day) tuples from photos."""
    # Returns [{year: 2026, month: 3, day: 15}, ...]
```

#### Task 1.3: Update Photos Endpoint
**File:** `backend/src/main.py`

```python
@app.get("/api/photos/")
def get_photos_endpoint(
    skip: int = Query(0),
    limit: int = Query(50),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    category_ids: Optional[list[int]] = Query(None),
    tag_ids: Optional[list[int]] = Query(None),
    camera_id: Optional[int] = Query(None),
    geoposition_id: Optional[int] = Query(None),
    year: Optional[int] = Query(None),          # NEW
    month: Optional[int] = Query(None),         # NEW
    day: Optional[int] = Query(None),           # NEW
) -> PaginatedResponse[PhotoSchema]:
    # Pass year, month, day to db_service
```

---

### PART 2: Frontend - Refactor Existing Filters to Use Modals

#### Task 2.1: Create Filter Bar Component
**File:** `frontend/src/components/ui/FilterBar.tsx` (NEW)

```typescript
interface FilterBarProps {
    selectedTags: number[]
    selectedCategories: number[]
    selectedCamera: number | null
    selectedGeo: number | null
    selectedYear: number | null
    selectedMonth: number | null
    selectedDay: number | null
    
    onTagSelect: (id: number) => void
    onCategorySelect: (id: number) => void
    onCameraSelect: (id: number | null) => void
    onGeoSelect: (id: number | null) => void
    onDateSelect: (year?: number, month?: number, day?: number) => void
    onReset: () => void
}

export function FilterBar({
    selectedTags,
    selectedCategories,
    selectedCamera,
    selectedGeo,
    selectedYear,
    selectedMonth,
    selectedDay,
    onTagSelect,
    onCategorySelect,
    onCameraSelect,
    onGeoSelect,
    onDateSelect,
    onReset,
}: FilterBarProps) {
    return (
        <div className="filter-bar">
            <button className="reset-btn" onClick={onReset}>Reset All</button>
            <TagsFilterButton {...} />
            <CategoriesFilterButton {...} />
            <CamerasFilterButton {...} />
            <GeopositionsFilterButton {...} />
            <DateFilterButton {...} />
        </div>
    )
}
```

#### Task 2.2: Create TagsFilterButton (Modal-Based)
**File:** `frontend/src/components/ui/TagsFilterButton.tsx` (NEW)

```typescript
interface TagsFilterButtonProps {
    selectedTags: number[]
    onSelect: (id: number) => void
}

export function TagsFilterButton({ selectedTags, onSelect }: TagsFilterButtonProps) {
    const [open, setOpen] = useState(false)
    const [tags, setTags] = useState<Tag[]>([])

    useEffect(() => {
        getTags().then(setTags)
    }, [])

    const displayText = selectedTags.length 
        ? `${selectedTags.length} tags` 
        : 'Tags'

    return (
        <>
            <button 
                className="filter-btn"
                onClick={() => setOpen(true)}
            >
                {displayText}
            </button>

            <Modal open={open} onClose={() => setOpen(false)} title="Filter by Tags">
                <div className="tag-selector">
                    {tags.map(tag => (
                        <button
                            key={tag.id}
                            className={`tag ${selectedTags.includes(tag.id) ? 'active' : ''}`}
                            onClick={() => {
                                onSelect(tag.id)
                                setOpen(false)  // Close on selection
                            }}
                        >
                            {tag.name}
                        </button>
                    ))}
                </div>
            </Modal>
        </>
    )
}
```

#### Task 2.3: Create CategoriesFilterButton (Modal-Based)
**File:** `frontend/src/components/ui/CategoriesFilterButton.tsx` (NEW)

Similar structure to TagsFilterButton but for categories (allows multiple selection).

#### Task 2.4: Create CamerasFilterButton (Modal-Based)
**File:** `frontend/src/components/ui/CamerasFilterButton.tsx` (NEW)

Similar structure but for cameras (single selection with "All" option).

#### Task 2.5: Create GeopositionsFilterButton (Modal-Based)
**File:** `frontend/src/components/ui/GeopositionsFilterButton.tsx` (NEW)

Similar structure but for geopositions (single selection with "All" option).

---

### PART 3: Frontend - Add Date Filtering with Cascading Modals

#### Task 3.1: Create DateFilterButton
**File:** `frontend/src/components/ui/DateFilterButton.tsx` (NEW)

```typescript
interface DateFilterButtonProps {
    selectedYear: number | null
    selectedMonth: number | null
    selectedDay: number | null
    onSelect: (year?: number, month?: number, day?: number) => void
}

export function DateFilterButton({
    selectedYear,
    selectedMonth,
    selectedDay,
    onSelect,
}: DateFilterButtonProps) {
    const [yearModalOpen, setYearModalOpen] = useState(false)
    const [monthModalOpen, setMonthModalOpen] = useState(false)
    const [dayModalOpen, setDayModalOpen] = useState(false)

    const [availableDates, setAvailableDates] = useState<Array<{year, month, day}>>([])

    useEffect(() => {
        getAvailableDates().then(setAvailableDates)
    }, [])

    const displayText = selectedYear
        ? selectedMonth
            ? selectedDay
                ? `${selectedYear}/${selectedMonth}/${selectedDay}`
                : `${selectedYear}/${selectedMonth}`
            : `${selectedYear}`
        : 'Date'

    const uniqueYears = [...new Set(availableDates.map(d => d.year))]
    const availableMonths = selectedYear
        ? [...new Set(availableDates.filter(d => d.year === selectedYear).map(d => d.month))]
        : []
    const availableDays = selectedYear && selectedMonth
        ? availableDates
            .filter(d => d.year === selectedYear && d.month === selectedMonth)
            .map(d => d.day)
            .sort((a, b) => a - b)
        : []

    return (
        <>
            <button onClick={() => setYearModalOpen(true)}>
                {displayText}
            </button>

            <Modal open={yearModalOpen} onClose={() => setYearModalOpen(false)} title="Select Year">
                <div className="year-selector">
                    {uniqueYears.map(year => (
                        <button
                            key={year}
                            onClick={() => {
                                onSelect(year)
                                setYearModalOpen(false)
                            }}
                        >
                            {year}
                        </button>
                    ))}
                    <button 
                        className="btn-secondary"
                        onClick={() => {
                            setYearModalOpen(false)
                            setMonthModalOpen(true)
                        }}
                    >
                        Months →
                    </button>
                </div>
            </Modal>

            <Modal open={monthModalOpen} onClose={() => setMonthModalOpen(false)} title="Select Month">
                <div className="month-selector">
                    <button 
                        className="btn-secondary"
                        onClick={() => {
                            setMonthModalOpen(false)
                            setYearModalOpen(true)
                        }}
                    >
                        ← Back
                    </button>

                    {availableMonths.map(month => (
                        <button
                            key={month}
                            onClick={() => {
                                onSelect(selectedYear, month)
                                setMonthModalOpen(false)
                            }}
                        >
                            {new Date(2000, month - 1).toLocaleString('default', { month: 'long' })}
                        </button>
                    ))}

                    <button 
                        className="btn-secondary"
                        onClick={() => {
                            setMonthModalOpen(false)
                            setDayModalOpen(true)
                        }}
                    >
                        Days →
                    </button>
                </div>
            </Modal>

            <Modal open={dayModalOpen} onClose={() => setDayModalOpen(false)} title="Select Day">
                <div className="day-selector">
                    <button 
                        className="btn-secondary"
                        onClick={() => {
                            setDayModalOpen(false)
                            setMonthModalOpen(true)
                        }}
                    >
                        ← Back
                    </button>

                    {availableDays.map(day => (
                        <button
                            key={day}
                            onClick={() => {
                                onSelect(selectedYear, selectedMonth, day)
                                setDayModalOpen(false)
                            }}
                        >
                            {day}
                        </button>
                    ))}
                </div>
            </Modal>
        </>
    )
}
```

---

### PART 4: Refactor GalleryPage

#### Task 4.1: Replace Sidebar with FilterBar
**File:** `frontend/src/pages/GalleryPage.tsx` (REFACTORED)

```typescript
export function GalleryPage() {
    const [selectedTags, setSelectedTags] = useState<number[]>([])
    const [selectedCategories, setSelectedCategories] = useState<number[]>([])
    const [selectedCamera, setSelectedCamera] = useState<number | null>(null)
    const [selectedGeo, setSelectedGeo] = useState<number | null>(null)
    const [selectedYear, setSelectedYear] = useState<number | null>(null)
    const [selectedMonth, setSelectedMonth] = useState<number | null>(null)
    const [selectedDay, setSelectedDay] = useState<number | null>(null)

    // ... rest of state ...

    useEffect(() => {
        getPhotos({
            skip: page * limit,
            limit,
            sort_by: sortBy,
            sort_order: sortOrder,
            category_ids: selectedCategories.length ? selectedCategories : undefined,
            tag_ids: selectedTags.length ? selectedTags : undefined,
            camera_id: selectedCamera ?? undefined,
            geoposition_id: selectedGeo ?? undefined,
            year: selectedYear ?? undefined,          // NEW
            month: selectedMonth ?? undefined,        // NEW
            day: selectedDay ?? undefined,            // NEW
        }).then(setData).finally(() => setLoading(false))
    }, [page, limit, selectedTags, selectedCategories, selectedCamera, selectedGeo, selectedYear, selectedMonth, selectedDay, sortBy, sortOrder])

    const resetFilters = () => {
        setSelectedTags([])
        setSelectedCategories([])
        setSelectedCamera(null)
        setSelectedGeo(null)
        setSelectedYear(null)                 // NEW
        setSelectedMonth(null)                // NEW
        setSelectedDay(null)                  // NEW
        setSortBy('created_at')
        setSortOrder('desc')
        setPage(0)
    }

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
                onTagSelect={id => {
                    setSelectedTags(prev => prev.includes(id) ? prev.filter(t => t !== id) : [...prev, id])
                    setPage(0)
                }}
                onCategorySelect={id => {
                    setSelectedCategories(prev => prev.includes(id) ? prev.filter(c => c !== id) : [...prev, c])
                    setPage(0)
                }}
                onCameraSelect={id => {
                    setSelectedCamera(id)
                    setPage(0)
                }}
                onGeoSelect={id => {
                    setSelectedGeo(id)
                    setPage(0)
                }}
                onDateSelect={(year, month, day) => {
                    setSelectedYear(year ?? null)
                    setSelectedMonth(month ?? null)
                    setSelectedDay(day ?? null)
                    setPage(0)
                }}
                onReset={resetFilters}
            />

            {/* Rest of gallery with photo grid and pagination */}
        </div>
    )
}
```

---

## Summary of New Components

| Component | File | Purpose |
|-----------|------|---------|
| FilterBar | `components/ui/FilterBar.tsx` | Container for all filter buttons |
| TagsFilterButton | `components/ui/TagsFilterButton.tsx` | Filter by tags (modal) |
| CategoriesFilterButton | `components/ui/CategoriesFilterButton.tsx` | Filter by categories (modal) |
| CamerasFilterButton | `components/ui/CamerasFilterButton.tsx` | Filter by cameras (modal) |
| GeopositionsFilterButton | `components/ui/GeopositionsFilterButton.tsx` | Filter by locations (modal) |
| DateFilterButton | `components/ui/DateFilterButton.tsx` | Filter by date with cascading modals |

---

## Test Plan (TDD)

### Backend Tests
- ✅ Date filter alone (year, month, day)
- ✅ Date filter + tags
- ✅ Date filter + all other filters
- ✅ Available dates endpoint
- ✅ Available dates with filter context

### Frontend Tests
- ✅ Each FilterButton component
- ✅ Modal opens/closes correctly
- ✅ Selection applies filter
- ✅ Date cascading modals work
- ✅ FilterBar integration with GalleryPage

### E2E Tests
- ✅ User can select each filter type
- ✅ User can combine multiple filters
- ✅ Filters persist during pagination
- ✅ Reset clears all filters

---

## File Changes Summary

### Backend (2 files)
1. `backend/src/db_service.py` - Add date filter params
2. `backend/src/main.py` - Add date params to endpoint, add available-dates endpoint

### Frontend (7 new files + 1 refactored)
**New:**
1. `frontend/src/components/ui/FilterBar.tsx`
2. `frontend/src/components/ui/TagsFilterButton.tsx`
3. `frontend/src/components/ui/CategoriesFilterButton.tsx`
4. `frontend/src/components/ui/CamerasFilterButton.tsx`
5. `frontend/src/components/ui/GeopositionsFilterButton.tsx`
6. `frontend/src/components/ui/DateFilterButton.tsx`
7. `frontend/src/components/ui/GalleryPage.css` (update styles)

**Refactored:**
1. `frontend/src/pages/GalleryPage.tsx` (remove sidebar, add FilterBar)

**Tests:**
1. Backend: Enhanced `test_main.py`, `test_db_service.py`
2. Frontend: Component tests for each button, integration tests, E2E tests

---

## Estimated Effort

| Phase | Task | Hours |
|-------|------|-------|
| **Backend** | Add date filters | 2 |
| **Frontend** | Filter buttons (5) | 5 |
| **Frontend** | Date cascading modals | 3 |
| **Frontend** | Refactor GalleryPage | 2 |
| **Testing** | Unit + E2E tests | 4 |
| **Styling** | Filter bar + modal CSS | 2 |
| **Refactoring** | Code cleanup | 1 |
| **Total** | | **19 hours** |

---

## Key Benefits of Modal-Based Approach

✅ Clean, minimal UI (filters hidden until clicked)  
✅ Better mobile experience (no sidebar clutter)  
✅ Intuitive for power users (cascading date selection)  
✅ Consistent UX across all filter types  
✅ Easy to add more filters in future  
✅ Reusable modal/button patterns
