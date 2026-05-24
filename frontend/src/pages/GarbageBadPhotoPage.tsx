import React, { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { getGarbageSummary, getGarbagePhotos, archivePhotos, deletePhoto, unmarkGarbage } from '@/api/client'
import type { PaginatedPhotos } from '@/types/api'
import { PhotoCard } from '@/components/photos/PhotoCard'
import { Spinner } from '@/components/ui/Spinner'
import { ConfirmModal } from '@/components/ui/ConfirmModal'
import './GarbageBadPhotoPage.css'

type PendingAction = { id: number; type: 'archive' | 'delete' } | null

// Maps API issue type keys to i18n keys under garbage.issues.*
const TECHNICAL_ISSUE_TYPES = [
    'thumbnail',
    'no_exif',
    'brightness',
    'edge_density',
    'blur',
    'entropy',
    'screenshot',
] as const

function IssueSection({
    issueType,
    count,
    onPhotoRemoved,
}: {
    issueType: string
    count: number
    onPhotoRemoved: () => void
}) {
    const { t } = useTranslation()
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
            const result = await getGarbagePhotos(issueType, 0, 50)
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

    const label = t(`garbage.issues.${issueType}`, { defaultValue: issueType })

    return (
        <div className="gbp-issue">
            <button className="gbp-issue__row" onClick={expand}>
                <span className="gbp-issue__label">{label}</span>
                {count > 0 && <span className="gbp-issue__count">{count}</span>}
                <span className="gbp-issue__chevron">{expanded ? '▲' : '▼'}</span>
            </button>

            {expanded && (
                <div className="gbp-issue__cards">
                    {loading && <Spinner />}
                    {!loading && visiblePhotos.length === 0 && (
                        <p className="gbp-issue__empty">{t('garbage.noFlagged')}</p>
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
                                title={t('garbage.notGarbageTitle')}
                            >
                                {t('garbage.notGarbage')}
                            </button>
                        </div>
                    ))}
                </div>
            )}

            <ConfirmModal
                open={pending !== null}
                title={pending?.type === 'delete' ? t('common.confirmDeletePhotoTitle') : t('common.confirmArchivePhotoTitle')}
                message={pending?.type === 'delete' ? t('common.confirmDeletePhotoMessage') : t('common.confirmArchivePhotoMessage')}
                confirmLabel={pending?.type === 'delete' ? t('common.delete') : t('common.archive')}
                variant={pending?.type === 'delete' ? 'danger' : 'warning'}
                onConfirm={executeAction}
                onClose={() => setPending(null)}
            />
        </div>
    )
}

function PlaceholderSection({ title }: { title: string }) {
    const { t } = useTranslation()
    return (
        <section className="gbp-section">
            <h2 className="gbp-section__heading">{title}</h2>
            <p className="gbp-section__placeholder">{t('garbage.comingSoon')}</p>
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
            {loading && <Spinner />}
            {error && <div className="gbp-page--error">{error}</div>}

            {!loading && !error && (
                <>
                    <section className="gbp-section">
                        <h2 className="gbp-section__heading">{t('garbage.technical')}</h2>
                        <div className="gbp-issues">
                            {TECHNICAL_ISSUE_TYPES.map(issueType => (
                                <IssueSection
                                    key={issueType}
                                    issueType={issueType}
                                    count={counts[issueType] ?? 0}
                                    onPhotoRemoved={() =>
                                        setCounts(prev => ({
                                            ...prev,
                                            [issueType]: Math.max(0, (prev[issueType] ?? 0) - 1),
                                        }))
                                    }
                                />
                            ))}
                        </div>
                    </section>

                    <div className="gbp-divider" />
                    <PlaceholderSection title={t('garbage.semantic')} />
                    <div className="gbp-divider" />
                    <PlaceholderSection title={t('garbage.temporary')} />
                    <div className="gbp-divider" />
                    <PlaceholderSection title={t('garbage.subjective')} />
                </>
            )}
        </div>
    )
}
