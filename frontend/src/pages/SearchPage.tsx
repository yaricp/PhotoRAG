import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { searchPhotos } from '@/api/client'
import { PhotoCard } from '@/components/photos/PhotoCard'
import { Spinner } from '@/components/ui/Spinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { useSearchStore } from '@/stores/useSearchStore'
import './SearchPage.css'

export function SearchPage() {
    const { t } = useTranslation()
    const { query, results, hasSearched, setQuery, setResults, clear } = useSearchStore()
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const onSearch = async () => {
        if (!query.trim()) return
        setLoading(true)
        setError(null)
        try {
            const data = await searchPhotos({ text_query: query, k: 10, thresholds: 1 })
            setResults(query, data)
        } catch {
            setError(t('search.error'))
        } finally {
            setLoading(false)
        }
    }


    const onClear = () => {
        clear()
        setError(null)
    }

    return (
        <div data-testid="page-search" className="search-page">
            <div className="search-page__toolbar">
                <input
                    className="search-page__input"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && onSearch()}
                    placeholder={t('search.placeholder')}
                />
                <button onClick={onSearch} disabled={loading || !query.trim()}>
                    {t('search.button')}
                </button>
                {hasSearched && (
                    <button className="search-page__clear-btn" onClick={onClear} disabled={loading}>
                        Clear
                    </button>
                )}
            </div>

            {loading && (
                <div className="search-page__center">
                    <Spinner size="lg" />
                </div>
            )}

            {error && (
                <div className="search-page__center">
                    <p className="search-page__error">{error}</p>
                </div>
            )}

            {!loading && !error && hasSearched && results.length === 0 && (
                <EmptyState
                    title={t('search.noResults')}
                    description="Try different search query"
                />
            )}

            {!loading && !error && results.length > 0 && (
                <div className="search-page__grid">
                    {results.map((result, index) => (
                        <div key={result.photo.id} className="search-page__result-item">
                            <span className="search-page__rank">#{index + 1}</span>
                            <span className="search-page__distance">dist {result.distance.toFixed(3)}</span>
                            <PhotoCard photo={result.photo} />
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}
