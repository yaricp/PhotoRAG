import React, { useCallback, useEffect, useState } from 'react'
import { getDuplicates, deletePhoto, archivePhoto, deleteDuplicateRecord } from '@/api/client'
import type { DuplicatesResponse, DuplicateGroup, ExactDuplicateEntry, PerceptualDuplicateEntry } from '@/api/client'
import { photoImageUrl } from '@/api/images'
import { Spinner } from '@/components/ui/Spinner'
import './DuplicatesPage.css'

function basename(path: string): string {
    return path.split('/').pop() ?? path
}

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

    return (
        <div className="dup-group">
            <div className="dup-group__original">
                <span className="dup-group__badge dup-group__badge--original">Original</span>
                <span className="dup-group__path" title={group.original.file_path}>
                    {basename(group.original.file_path)}
                </span>
                <span className="dup-group__full-path">{group.original.file_path}</span>
            </div>
            <div className="dup-group__duplicates">
                {group.duplicates.map((d) => (
                    <label key={d.id} className="dup-group__item">
                        <input
                            type="checkbox"
                            checked={selected.has(d.id)}
                            onChange={() => toggle(d.id)}
                            className="dup-group__checkbox"
                        />
                        <span className="dup-group__path" title={d.file_path}>
                            {basename(d.file_path)}
                        </span>
                        <span className="dup-group__full-path">{d.file_path}</span>
                    </label>
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

function PerceptualCard({ dup, onDeleted, onArchived }: {
    dup: PerceptualDuplicateEntry
    onDeleted: () => void
    onArchived: () => void
}) {
    const [busy, setBusy] = useState<'delete' | 'archive' | null>(null)

    async function handleDelete() {
        setBusy('delete')
        try {
            await deletePhoto(dup.id)
            onDeleted()
        } finally {
            setBusy(null)
        }
    }

    async function handleArchive() {
        setBusy('archive')
        try {
            await archivePhoto(dup.id)
            onArchived()
        } finally {
            setBusy(null)
        }
    }

    return (
        <div className="dup-card">
            <div className="dup-card__image-wrap">
                <img
                    src={photoImageUrl(dup.file_path)}
                    alt={basename(dup.file_path)}
                    className="dup-card__image"
                    loading="lazy"
                />
                <span className="dup-card__dist">dist {dup.hash_distance}</span>
            </div>
            <div className="dup-card__body">
                <span className="dup-card__name" title={dup.file_path}>
                    {basename(dup.file_path)}
                </span>
                <div className="dup-card__actions">
                    <button
                        className="dup-card__btn dup-card__btn--archive"
                        onClick={handleArchive}
                        disabled={busy !== null}
                    >
                        {busy === 'archive' ? '…' : 'Archive'}
                    </button>
                    <button
                        className="dup-card__btn dup-card__btn--delete"
                        onClick={handleDelete}
                        disabled={busy !== null}
                    >
                        {busy === 'delete' ? '…' : 'Delete'}
                    </button>
                </div>
            </div>
        </div>
    )
}

function PerceptualGroup({ group, onReload }: {
    group: DuplicateGroup<PerceptualDuplicateEntry>
    onReload: () => void
}) {
    return (
        <div className="dup-group">
            <div className="dup-group__original">
                <span className="dup-group__badge dup-group__badge--original">Original</span>
                <div className="dup-group__original-preview">
                    <img
                        src={photoImageUrl(group.original.file_path)}
                        alt={basename(group.original.file_path)}
                        className="dup-group__original-thumb"
                        loading="lazy"
                    />
                    <div>
                        <span className="dup-group__path" title={group.original.file_path}>
                            {basename(group.original.file_path)}
                        </span>
                        <span className="dup-group__full-path">{group.original.file_path}</span>
                    </div>
                </div>
            </div>
            <div className="dup-cards">
                {group.duplicates.map((d) => (
                    <PerceptualCard
                        key={d.id}
                        dup={d}
                        onDeleted={onReload}
                        onArchived={onReload}
                    />
                ))}
            </div>
        </div>
    )
}

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
