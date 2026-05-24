import React, { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { getGarbageSummary, getGarbagePhotos, archivePhotos, deletePhoto, unmarkGarbage } from '@/api/client'
import type { PaginatedPhotos } from '@/types/api'
import { PhotoCard } from '@/components/photos/PhotoCard'
import { Spinner } from '@/components/ui/Spinner'
import { ConfirmModal } from '@/components/ui/ConfirmModal'
import './GarbageBadPhotoPage.css'

type PendingAction = { id: number; type: 'archive' | 'delete' } | null

interface IssueRow {
    type: string
    label: string
}

const TECHNICAL_ISSUES: IssueRow[] = [
    { type: 'thumbnail',     label: 'Thumbnails (resolution too small)' },
    { type: 'no_exif',       label: 'No EXIF (possible internet copy)' },
    { type: 'brightness',    label: 'Abnormal brightness' },
    { type: 'edge_density',  label: 'Low edge density (featureless)' },
    { type: 'blur',          label: 'Blurry (Laplacian)' },
    { type: 'entropy',       label: 'Low entropy (low information)' },
    { type: 'screenshot',    label: 'Screenshots (UI detected)' },
]

function IssueSection({
    issue,
    count,
    onPhotoRemoved,
}: {
    issue: IssueRow
    count: number
    onPhotoRemoved: () => void
}) {
    const [expanded, setExpanded] = useState(false)
    const [data, setData] = useState<PaginatedPhotos | null>(null)
    const [loading, setLoading] = useState(false)
    const [ids, setIds] = useState<Set<number>>(new Set())
    const [pending, setPending] = useState<PendingAction>(null)

    async function expand() {
        if (expanded) { setExpanded(false); return }
        setExpanded(true)
        if (data) return
        setLoading(true)
        try {
            const result = await getGarbagePhotos(issue.type, 0, 50)
            setData(result)
            setIds(new Set(result.items.map(p => p.id)))
        } finally {
            setLoading(false)
        }
    }

    function removeCard(id: number) {
        setIds(prev => { const next = new Set(prev); next.delete(id); return next })
        onPhotoRemoved()
    }

    async function executeAction() {
        if (!pending) return
        const { id, type } = pending
        if (type === 'archive') await archivePhotos([id])
        else await deletePhoto(id)
        removeCard(id)
    }

    async function handleNotGarbage(id: number) {
        await unmarkGarbage(id)
        removeCard(id)
    }

    const visiblePhotos = data?.items.filter(p => ids.has(p.id)) ?? []

    const confirmTitle = pending?.type === 'delete' ? 'Delete photo?' : 'Archive photo?'
    const confirmMessage = pending?.type === 'delete'
        ? 'This file will be permanently removed from disk.'
        : 'This photo will be marked as archived.'

    return (
        <div className="gbp-issue">
            <button className="gbp-issue__row" onClick={expand}>
                <span className="gbp-issue__label">{issue.label}</span>
                {count > 0 && <span className="gbp-issue__count">{count}</span>}
                <span className="gbp-issue__chevron">{expanded ? '▲' : '▼'}</span>
            </button>

            {expanded && (
                <div className="gbp-issue__cards">
                    {loading && <Spinner />}
                    {!loading && visiblePhotos.length === 0 && (
                        <p className="gbp-issue__empty">No photos flagged.</p>
                    )}
                    {!loading && visiblePhotos.map(photo => (
                        <div key={photo.id} className="gbp-card-wrap">
                            <PhotoCard
                                photo={photo}
                                onArchive={() => setPending({ id: photo.id, type: 'archive' })}
                                onDelete={() => setPending({ id: photo.id, type: 'delete' })}
                            />
                            <button
                                className="gbp-not-garbage-btn"
                                onClick={() => handleNotGarbage(photo.id)}
                                title="Remove all garbage flags from this photo"
                            >
                                Not garbage
                            </button>
                        </div>
                    ))}
                </div>
            )}

            <ConfirmModal
                open={pending !== null}
                title={confirmTitle}
                message={confirmMessage}
                confirmLabel={pending?.type === 'delete' ? 'Delete' : 'Archive'}
                variant={pending?.type === 'delete' ? 'danger' : 'warning'}
                onConfirm={executeAction}
                onClose={() => setPending(null)}
            />
        </div>
    )
}

function PlaceholderSection({ title }: { title: string }) {
    return (
        <section className="gbp-section">
            <h2 className="gbp-section__heading">{title}</h2>
            <p className="gbp-section__placeholder">Coming soon</p>
        </section>
    )
}

export function GarbageBadPhotoPage() {
    const { t } = useTranslation()
    const [counts, setCounts] = useState<Record<string, number>>({})
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    const load = useCallback(async () => {
        setLoading(true)
        setError(null)
        try {
            const summary = await getGarbageSummary()
            setCounts(summary.counts ?? {})
        } catch {
            setError(t('garbage.error'))
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => { load() }, [load])

    return (
        <div className="gbp-page">
            <h1 className="gbp-page__title">{t('garbage.title')}</h1>

            {loading && <Spinner />}
            {error && <div className="gbp-page--error">{error}</div>}

            {!loading && !error && (
                <>
                    <section className="gbp-section">
                        <h2 className="gbp-section__heading">Technical Garbage</h2>
                        <div className="gbp-issues">
                            {TECHNICAL_ISSUES.map(issue => (
                                <IssueSection
                                    key={issue.type}
                                    issue={issue}
                                    count={counts[issue.type] ?? 0}
                                    onPhotoRemoved={() =>
                                        setCounts(prev => ({
                                            ...prev,
                                            [issue.type]: Math.max(0, (prev[issue.type] ?? 0) - 1),
                                        }))
                                    }
                                />
                            ))}
                        </div>
                    </section>

                    <div className="gbp-divider" />
                    <PlaceholderSection title="Semantic Garbage" />
                    <div className="gbp-divider" />
                    <PlaceholderSection title="Temporary Garbage" />
                    <div className="gbp-divider" />
                    <PlaceholderSection title="Subjective Garbage" />
                </>
            )}
        </div>
    )
}
