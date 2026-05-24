import React, { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { getDuplicates, deletePhoto, archivePhotos, deleteDuplicateRecord } from '@/api/client'
import type { DuplicatesResponse, DuplicateGroup, ExactDuplicateEntry, PerceptualDuplicateEntry } from '@/api/client'
import { photoImageUrl } from '@/api/images'
import { Spinner } from '@/components/ui/Spinner'
import { ConfirmModal } from '@/components/ui/ConfirmModal'
import './DuplicatesPage.css'

function basename(path: string): string {
    return path.split('/').pop() ?? path
}

// ─── Shared photo card ───────────────────────────────────────────────────────

function DupPhotoCard({
    filePath,
    photoId,
    badge,
    onArchive,
    onDelete,
    checked,
    onCheck,
}: {
    filePath: string
    photoId?: number
    badge?: React.ReactNode
    onArchive?: () => void
    onDelete?: () => void
    checked?: boolean
    onCheck?: () => void
}) {
    const { t } = useTranslation()

    return (
        <div className={`dup-card${checked ? ' dup-card--selected' : ''}`}>
            <div className="dup-card__image-wrap">
                <img
                    src={photoImageUrl(filePath)}
                    alt={basename(filePath)}
                    className="dup-card__image"
                    loading="lazy"
                />
                {photoId !== undefined && (
                    <span className="dup-card__id-badge">#{photoId}</span>
                )}
                {badge}
                {onCheck !== undefined && (
                    <input
                        type="checkbox"
                        className="dup-card__checkbox"
                        checked={checked ?? false}
                        onChange={onCheck}
                    />
                )}
            </div>
            <div className="dup-card__body">
                <span className="dup-card__name" title={filePath}>
                    {basename(filePath)}
                </span>
                {(onArchive || onDelete) && (
                    <div className="dup-card__actions">
                        {onArchive && (
                            <button className="dup-card__btn dup-card__btn--archive" onClick={onArchive}>
                                {t('duplicates.archive')}
                            </button>
                        )}
                        {onDelete && (
                            <button className="dup-card__btn dup-card__btn--delete" onClick={onDelete}>
                                {t('duplicates.delete')}
                            </button>
                        )}
                    </div>
                )}
            </div>
        </div>
    )
}

// ─── Exact duplicates section (selection lifted here) ────────────────────────

function ExactDuplicatesSection({ groups, onReload }: {
    groups: DuplicateGroup<ExactDuplicateEntry>[]
    onReload: () => void
}) {
    const { t } = useTranslation()
    // Flat set of all selected duplicate record IDs across all groups
    const [selected, setSelected] = useState<Set<number>>(new Set())
    const [deleting, setDeleting] = useState(false)
    const [confirmOpen, setConfirmOpen] = useState(false)

    const allDupIds = groups.flatMap(g => g.duplicates.map(d => d.id))
    const allSelected = allDupIds.length > 0 && allDupIds.every(id => selected.has(id))
    const someSelected = selected.size > 0 && !allSelected

    function toggle(id: number) {
        setSelected(prev => {
            const next = new Set(prev)
            next.has(id) ? next.delete(id) : next.add(id)
            return next
        })
    }

    function toggleAll() {
        setSelected(allSelected ? new Set() : new Set(allDupIds))
    }

    async function handleDeleteSelected() {
        if (selected.size === 0) return
        setDeleting(true)
        try {
            await Promise.all([...selected].map(id => deleteDuplicateRecord(id)))
            onReload()
        } finally {
            setDeleting(false)
            setSelected(new Set())
        }
    }

    const originalBadge = (
        <span className="dup-card__badge dup-card__badge--original">{t('duplicates.original')}</span>
    )

    const totalExact = groups.reduce((s, g) => s + g.duplicates.length, 0)

    return (
        <section className="dup-section">
            <h2 className="dup-section__heading">
                {allDupIds.length > 0 && (
                    <input
                        type="checkbox"
                        className="dup-section__select-all"
                        checked={allSelected}
                        ref={el => { if (el) el.indeterminate = someSelected }}
                        onChange={toggleAll}
                        title={t('duplicates.selectAll')}
                    />
                )}
                {t('duplicates.exact')}
                <span className="dup-section__count">{totalExact}</span>
                <button
                    className="dup-section__delete-btn"
                    onClick={() => setConfirmOpen(true)}
                    disabled={deleting || selected.size === 0}
                >
                    {deleting
                        ? t('duplicates.deleting')
                        : selected.size > 0
                            ? t('duplicates.deleteSelected', { count: selected.size })
                            : t('duplicates.deleteSelectedEmpty')}
                </button>
            </h2>

            {groups.length === 0 ? (
                <p className="dup-section__empty">{t('duplicates.noExact')}</p>
            ) : (
                groups.map((g, i) => (
                    <div key={i} className="dup-group">
                        <div className="dup-cards">
                            <DupPhotoCard filePath={g.original.file_path} photoId={g.original.id} badge={originalBadge} />
                            {g.duplicates.map((d) => (
                                <DupPhotoCard
                                    key={d.id}
                                    filePath={d.file_path}
                                    checked={selected.has(d.id)}
                                    onCheck={() => toggle(d.id)}
                                />
                            ))}
                        </div>
                    </div>
                ))
            )}

            <ConfirmModal
                open={confirmOpen}
                title={t('duplicates.confirmDeleteCountTitle', { count: selected.size })}
                message={t('duplicates.confirmBulkDeleteMessage')}
                confirmLabel={t('duplicates.delete')}
                variant="danger"
                onConfirm={handleDeleteSelected}
                onClose={() => setConfirmOpen(false)}
            />
        </section>
    )
}

// ─── Perceptual duplicates group ─────────────────────────────────────────────

function PerceptualGroup({ group, onReload }: {
    group: DuplicateGroup<PerceptualDuplicateEntry>
    onReload: () => void
}) {
    const { t } = useTranslation()
    const [busy, setBusy] = useState<Record<number, 'delete' | 'archive'>>({})
    const [pending, setPending] = useState<{ id: number; type: 'delete' | 'archive' } | null>(null)

    async function executeAction() {
        if (!pending) return
        const { id, type } = pending
        setBusy(prev => ({ ...prev, [id]: type }))
        try {
            if (type === 'delete') await deletePhoto(id)
            else await archivePhotos([id])
            onReload()
        } finally {
            setBusy(prev => { const next = { ...prev }; delete next[id]; return next })
        }
    }

    const origId = group.original.id

    return (
        <div className="dup-group">
            <div className="dup-cards">
                <DupPhotoCard
                    filePath={group.original.file_path}
                    photoId={origId}
                    onArchive={busy[origId] ? undefined : () => setPending({ id: origId, type: 'archive' })}
                    onDelete={busy[origId] ? undefined : () => setPending({ id: origId, type: 'delete' })}
                />
                {group.duplicates.map((d) => (
                    <DupPhotoCard
                        key={d.id}
                        filePath={d.file_path}
                        photoId={d.id}
                        badge={<span className="dup-card__dist">dist {d.hash_distance}</span>}
                        onArchive={busy[d.id] ? undefined : () => setPending({ id: d.id, type: 'archive' })}
                        onDelete={busy[d.id] ? undefined : () => setPending({ id: d.id, type: 'delete' })}
                    />
                ))}
            </div>

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

// ─── Page ────────────────────────────────────────────────────────────────────

export function DuplicatesPage() {
    const { t } = useTranslation()
    const [data, setData] = useState<DuplicatesResponse | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    const load = useCallback(async () => {
        setLoading(true)
        setError(null)
        try {
            setData(await getDuplicates())
        } catch {
            setError(t('duplicates.error'))
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => { load() }, [load])

    return (
        <div className="dup-page">
            {loading && <Spinner />}
            {error && <div className="dup-page--error">{error}</div>}

            {!loading && !error && data && (
                <>
                    <ExactDuplicatesSection groups={data.exact} onReload={load} />

                    <div className="dup-divider" />

                    <section className="dup-section">
                        <h2 className="dup-section__heading">
                            {t('duplicates.perceptual')}
                            <span className="dup-section__count">
                                {data.perceptual.reduce((s, g) => s + g.duplicates.length, 0)}
                            </span>
                        </h2>
                        {data.perceptual.length === 0 ? (
                            <p className="dup-section__empty">{t('duplicates.noNear')}</p>
                        ) : (
                            data.perceptual.map((g, i) => (
                                <PerceptualGroup key={i} group={g} onReload={load} />
                            ))
                        )}
                    </section>
                </>
            )}
        </div>
    )
}
