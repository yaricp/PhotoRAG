import React, { useCallback, useEffect, useState } from 'react'
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
    badge,
    onArchive,
    onDelete,
    checked,
    onCheck,
}: {
    filePath: string
    badge?: React.ReactNode
    onArchive?: () => void
    onDelete?: () => void
    checked?: boolean
    onCheck?: () => void
}) {
    return (
        <div className={`dup-card${checked ? ' dup-card--selected' : ''}`}>
            <div className="dup-card__image-wrap">
                <img
                    src={photoImageUrl(filePath)}
                    alt={basename(filePath)}
                    className="dup-card__image"
                    loading="lazy"
                />
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
                                Archive
                            </button>
                        )}
                        {onDelete && (
                            <button className="dup-card__btn dup-card__btn--delete" onClick={onDelete}>
                                Delete
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
    // Flat set of all selected duplicate record IDs across all groups
    const [selected, setSelected] = useState<Set<number>>(new Set())
    const [deleting, setDeleting] = useState(false)
    const [confirmOpen, setConfirmOpen] = useState(false)

    function toggle(id: number) {
        setSelected(prev => {
            const next = new Set(prev)
            next.has(id) ? next.delete(id) : next.add(id)
            return next
        })
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
        <span className="dup-card__badge dup-card__badge--original">Original</span>
    )

    const totalExact = groups.reduce((s, g) => s + g.duplicates.length, 0)

    return (
        <section className="dup-section">
            <h2 className="dup-section__heading">
                Exact duplicates
                <span className="dup-section__count">{totalExact}</span>
                <button
                    className="dup-section__delete-btn"
                    onClick={() => setConfirmOpen(true)}
                    disabled={deleting || selected.size === 0}
                >
                    {deleting
                        ? 'Deleting…'
                        : `Delete selected${selected.size > 0 ? ` (${selected.size})` : ''}`}
                </button>
            </h2>

            {groups.length === 0 ? (
                <p className="dup-section__empty">No exact duplicates found.</p>
            ) : (
                groups.map((g, i) => (
                    <div key={i} className="dup-group">
                        <div className="dup-cards">
                            <DupPhotoCard filePath={g.original.file_path} badge={originalBadge} />
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
                title={`Delete ${selected.size} duplicate${selected.size !== 1 ? 's' : ''}?`}
                message="The selected duplicate records will be permanently deleted from disk."
                confirmLabel="Delete"
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

    const originalBadge = (
        <span className="dup-card__badge dup-card__badge--original">Original</span>
    )

    return (
        <div className="dup-group">
            <div className="dup-cards">
                <DupPhotoCard filePath={group.original.file_path} badge={originalBadge} />
                {group.duplicates.map((d) => (
                    <DupPhotoCard
                        key={d.id}
                        filePath={d.file_path}
                        badge={<span className="dup-card__dist">dist {d.hash_distance}</span>}
                        onArchive={busy[d.id] ? undefined : () => setPending({ id: d.id, type: 'archive' })}
                        onDelete={busy[d.id] ? undefined : () => setPending({ id: d.id, type: 'delete' })}
                    />
                ))}
            </div>

            <ConfirmModal
                open={pending !== null}
                title={pending?.type === 'delete' ? 'Delete photo?' : 'Archive photo?'}
                message={pending?.type === 'delete'
                    ? 'This file will be permanently removed from disk.'
                    : 'This photo will be marked as archived.'}
                confirmLabel={pending?.type === 'delete' ? 'Delete' : 'Archive'}
                variant={pending?.type === 'delete' ? 'danger' : 'warning'}
                onConfirm={executeAction}
                onClose={() => setPending(null)}
            />
        </div>
    )
}

// ─── Page ────────────────────────────────────────────────────────────────────

export function DuplicatesPage() {
    const [data, setData] = useState<DuplicatesResponse | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    const load = useCallback(async () => {
        setLoading(true)
        setError(null)
        try {
            setData(await getDuplicates())
        } catch {
            setError('Failed to load duplicates')
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => { load() }, [load])

    if (loading) return <div className="dup-page"><Spinner /></div>
    if (error) return <div className="dup-page dup-page--error">{error}</div>
    if (!data) return null

    const totalPerceptual = data.perceptual.reduce((s, g) => s + g.duplicates.length, 0)

    return (
        <div className="dup-page">
            <h1 className="dup-page__title">Duplicates</h1>

            <ExactDuplicatesSection groups={data.exact} onReload={load} />

            <div className="dup-divider" />

            <section className="dup-section">
                <h2 className="dup-section__heading">
                    Near-duplicates
                    <span className="dup-section__count">{totalPerceptual}</span>
                </h2>
                {data.perceptual.length === 0 ? (
                    <p className="dup-section__empty">No near-duplicates found.</p>
                ) : (
                    data.perceptual.map((g, i) => (
                        <PerceptualGroup key={i} group={g} onReload={load} />
                    ))
                )}
            </section>
        </div>
    )
}
