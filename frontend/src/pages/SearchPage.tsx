import { useState } from 'react'
import { searchPhotos } from '@/api/client'
import { PhotoCard } from '@/components/photos/PhotoCard'
import { Spinner } from '@/components/ui/Spinner'
import { EmptyState } from '@/components/ui/EmptyState'
import type { Photo } from '@/types/api'
import './SearchPage.css'

export function SearchPage() {
    const [query, setQuery] = useState('')
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [results, setResults] = useState<Photo[]>([])

    const onSearch = async () => {
        if (!query.trim()) return

        setLoading(true)
        setError(null)

        try {
            const data = await searchPhotos({
                text_query: query,
                k: 10,
                thresholds: 1,
            })
            setResults(data)
        } catch {
            setError('Failed to search photos')
        } finally {
            setLoading(false)
        }
    }

    return (
        <div data-testid="page-search" className="search-page">
            {/* SEARCH BAR (как toolbar в Gallery) */}
            <div className="search-page__toolbar">
                <input
                    className="search-page__input"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Search photos..."
                />
                <button onClick={onSearch}>
                    Search
                </button>
            </div>

            {/* LOADING */}
            {loading && (
                <div className="search-page__center">
                    <Spinner size="lg" />
                </div>
            )}

            {/* ERROR */}
            {error && (
                <div className="search-page__center">
                    <p className="search-page__error">{error}</p>
                </div>
            )}

            {/* EMPTY STATE */}
            {!loading && !error && results.length === 0 && (
                <EmptyState
                    title="No results"
                    description="Try different search query"
                />
            )}

            {/* GRID (ТОЧНО КАК В GALLERY) */}
            {!loading && !error && results.length > 0 && (
                <div className="search-page__grid">
                    {results.map(photo => (
                        <PhotoCard key={photo.id} photo={photo} />
                    ))}
                </div>
            )}
        </div>
    )
}