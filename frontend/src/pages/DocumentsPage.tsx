import React, { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { getPhotos } from '@/api/client'
import { PhotoCard } from '@/components/photos/PhotoCard'
import { Spinner } from '@/components/ui/Spinner'
import { EmptyState } from '@/components/ui/EmptyState'
import type { Photo } from '@/types/api'
import './DocumentsPage.css'

const LIMIT = 50

export function DocumentsPage() {
    const { t } = useTranslation()
    const [data, setData] = useState<Photo[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [page, setPage] = useState(0)

    useEffect(() => {
        setLoading(true)
        setError(null)

        getPhotos({
            skip: page * LIMIT,
            limit: LIMIT,
            sort_by: 'id',
            sort_order: 'asc',
            is_doc: true,
        })
            .then((res) => setData(res.items))
            .catch(() => setError(t('documents.failedToLoad')))
            .finally(() => setLoading(false))
    }, [page])

    return (
        <div data-testid="page-documents" className="documents-page">

            {/* LOADING */}
            {loading && (
                <div className="documents-page__center">
                    <Spinner size="lg" />
                </div>
            )}

            {/* ERROR */}
            {error && (
                <div className="documents-page__center">
                    <p className="documents-page__error">{error}</p>
                </div>
            )}

            {/* EMPTY */}
            {!loading && !error && data.length === 0 && (
                <EmptyState
                    title={t('documents.noDocuments')}
                    description={t('documents.noDocumentsDesc')}
                />
            )}

            {/* GRID */}
            {!loading && !error && data.length > 0 && (
                <div className="documents-page__grid">
                    {data.map(photo => (
                        <PhotoCard key={photo.id} photo={photo} />
                    ))}
                </div>
            )}
        </div>
    )
}