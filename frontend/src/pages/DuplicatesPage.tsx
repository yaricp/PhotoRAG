import React, { useCallback, useEffect, useState } from 'react'
import { getDuplicates, deletePhoto, archivePhoto, deleteDuplicateRecord } from '@/api/client'
import type { DuplicatesResponse, DuplicateGroup, ExactDuplicateEntry, PerceptualDuplicateEntry } from '@/api/client'
import { photoImageUrl } from '@/api/images'
import { Spinner } from '@/components/ui/Spinner'
import './DuplicatesPage.css'

function basename(path: string): string {
    return path.split('/').pop() ?? path
}

// ─── Shared photo card used in both sections ────────────────────────────────

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

// ─── Exact duplicates group ─────────────────────────────────────────────────

function ExactGroup({ group, onReload }: {
    group: DuplicateGroup<ExactDuplicateEntry>
    onReload: () => void
}) {
    const [selected, setSelected] = useState<Set<number>>(new Set())
    const [deleting, setDeleting] = useState(false)

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
                        checked={selected.has(d.id)}
                        onCheck={() => toggle(d.id)}
                    />
                ))}
            </div>
            <div className="dup-group__actions">
                <button
                    className="dup-group__delete-btn"
                    onClick={handleDeleteSelected}
                    disabled={deleting || selected.size === 0}
                >
                    {deleting ? 'Deleting…' : `Delete selected${selected.size > 0 ? ` (${selected.size})` : ''}`}
                </button>
            </div>
        </div>
    )
}

// ─── Perceptual duplicates group ────────────────────────────────────────────

function PerceptualGroup({ group, onReload }: {
    group: DuplicateGroup<PerceptualDuplicateEntry>
    onReload: () => void
}) {
    const [busy, setBusy] = useState<Record<number, 'delete' | 'archive'>>({})

    async function handleDelete(id: number) {
        setBusy(prev => ({ ...prev, [id]: 'delete' }))
        try { await deletePhoto(id); onReload() }
        finally { setBusy(prev => { const next = { ...prev }; delete next[id]; return next }) }
    }

    async function handleArchive(id: number) {
        setBusy(prev => ({ ...prev, [id]: 'archive' }))
        try { await archivePhoto(id); onReload() }
        finally { setBusy(prev => { const next = { ...prev }; delete next[id]; return next }) }
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
                        onArchive={busy[d.id] ? undefined : () => handleArchive(d.id)}
                        onDelete={busy[d.id] ? undefined : () => handleDelete(d.id)}
                    />
                ))}
            </div>
        </div>
    )
}

// ─── Page ───────────────────────────────────────────────────────────────────

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

    const totalExact = data.exact.reduce((s, g) => s + g.duplicates.length, 0)
    const totalPerceptual = data.perceptual.reduce((s, g) => s + g.duplicates.length, 0)

    return (
        <div className="dup-page">
            <h1 className="dup-page__title">Duplicates</h1>

            <section className="dup-section">
                <h2 className="dup-section__heading">
                    Exact duplicates
                    <span className="dup-section__count">{totalExact}</span>
                </h2>
                {data.exact.length === 0 ? (
                    <p className="dup-section__empty">No exact duplicates found.</p>
                ) : (
                    data.exact.map((g, i) => (
                        <ExactGroup key={i} group={g} onReload={load} />
                    ))
                )}
            </section>

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
