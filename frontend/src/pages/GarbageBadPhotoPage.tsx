import React, { useCallback, useEffect, useState } from 'react'
import { getGarbageSummary, getGarbagePhotos, archivePhoto, deletePhoto } from '@/api/client'
import type { GarbageSummary } from '@/api/client'
import type { PaginatedPhotos } from '@/types/api'
import { PhotoCard } from '@/components/photos/PhotoCard'
import { Spinner } from '@/components/ui/Spinner'
import './GarbageBadPhotoPage.css'

interface IssueRow {
    type: string
    label: string
}

const TECHNICAL_ISSUES: IssueRow[] = [
    { type: 'thumbnail',     label: 'Thumbnails (resolution too small)' },
    { type: 'no_exif',      label: 'No EXIF (possible internet copy)' },
    { type: 'brightness',   label: 'Abnormal brightness' },
    { type: 'edge_density', label: 'Low edge density (featureless)' },
    { type: 'blur',         label: 'Blurry (Laplacian)' },
    { type: 'entropy',      label: 'Low entropy (low information)' },
    { type: 'screenshot',   label: 'Screenshots (UI detected)' },
]

function IssueSection({ issue, count }: { issue: IssueRow; count: number }) {
    const [expanded, setExpanded] = useState(false)
    const [data, setData] = useState<PaginatedPhotos | null>(null)
    const [loading, setLoading] = useState(false)
    const [ids, setIds] = useState<Set<number>>(new Set())

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
    }

    async function handleArchive(id: number) {
        await archivePhoto(id)
        removeCard(id)
    }

    async function handleDelete(id: number) {
        await deletePhoto(id)
        removeCard(id)
    }

    const visiblePhotos = data?.items.filter(p => ids.has(p.id)) ?? []

    return (
        <div className="gbp-issue">
            <button className="gbp-issue__row" onClick={expand}>
                <span className="gbp-issue__label">{issue.label}</span>
                {count > 0 && (
                    <span className="gbp-issue__count">{count}</span>
                )}
                <span className="gbp-issue__chevron">{expanded ? '▲' : '▼'}</span>
            </button>

            {expanded && (
                <div className="gbp-issue__cards">
                    {loading && <Spinner />}
                    {!loading && visiblePhotos.length === 0 && (
                        <p className="gbp-issue__empty">No photos flagged.</p>
                    )}
                    {!loading && visiblePhotos.map(photo => (
                        <PhotoCard
                            key={photo.id}
                            photo={photo}
                            onArchive={() => handleArchive(photo.id)}
                            onDelete={() => handleDelete(photo.id)}
                        />
                    ))}
                </div>
            )}
        </div>
    )
}

interface PlaceholderSectionProps { title: string }

function PlaceholderSection({ title }: PlaceholderSectionProps) {
    return (
        <section className="gbp-section">
            <h2 className="gbp-section__heading">{title}</h2>
            <p className="gbp-section__placeholder">Coming soon</p>
        </section>
    )
}

export function GarbageBadPhotoPage() {
    const [summary, setSummary] = useState<GarbageSummary | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    const load = useCallback(async () => {
        setLoading(true)
        setError(null)
        try {
            setSummary(await getGarbageSummary())
        } catch {
            setError('Failed to load garbage summary')
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => { load() }, [load])

    if (loading) return <div className="gbp-page"><Spinner /></div>
    if (error) return <div className="gbp-page gbp-page--error">{error}</div>

    const counts = summary?.counts ?? {}

    return (
        <div className="gbp-page">
            <h1 className="gbp-page__title">Garbage &amp; Bad Photos</h1>

            <section className="gbp-section">
                <h2 className="gbp-section__heading">Technical Garbage</h2>
                <div className="gbp-issues">
                    {TECHNICAL_ISSUES.map(issue => (
                        <IssueSection
                            key={issue.type}
                            issue={issue}
                            count={counts[issue.type] ?? 0}
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
        </div>
    )
}
