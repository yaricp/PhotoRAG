import React, { useEffect, useState, useCallback } from 'react'
import { Modal } from '@/components/ui/Modal'
import { getTemplateCategories, linkPhotoCategory, unlinkPhotoCategory } from '@/api/client'
import type { TemplateCategory, LinkedCategory } from '@/api/client'
import './TagPickerModal.css'

interface Props {
    open: boolean
    photoId: number
    linkedCategories: LinkedCategory[]
    onClose: () => void
    onChanged: (linked: LinkedCategory[]) => void
}

export function CategoryPickerModal({ open, photoId, linkedCategories, onClose, onChanged }: Props) {
    const [all, setAll] = useState<TemplateCategory[]>([])
    const [search, setSearch] = useState('')
    const [current, setCurrent] = useState<LinkedCategory[]>(linkedCategories)
    const [loading, setLoading] = useState(false)

    useEffect(() => { setCurrent(linkedCategories) }, [linkedCategories])

    const load = useCallback(async () => {
        setLoading(true)
        try {
            let skip = 0
            const pageSize = 50
            const result: TemplateCategory[] = []
            while (true) {
                const page = await getTemplateCategories(skip, pageSize)
                result.push(...page.items)
                if (result.length >= page.total) break
                skip += pageSize
            }
            setAll(result)
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => { if (open) load() }, [open, load])

    const isLinked = (cat: TemplateCategory) => current.some(lc => lc.name === cat.name)

    async function toggle(cat: TemplateCategory) {
        const linked = current.find(lc => lc.name === cat.name)
        if (linked) {
            await unlinkPhotoCategory(photoId, linked.id)
            const next = current.filter(lc => lc.name !== cat.name)
            setCurrent(next)
            onChanged(next)
        } else {
            const lc = await linkPhotoCategory(photoId, cat.name)
            const next = [...current, lc]
            setCurrent(next)
            onChanged(next)
        }
    }

    const filtered = all.filter(c =>
        c.name.toLowerCase().includes(search.toLowerCase())
    )
    const sorted = [
        ...filtered.filter(c => isLinked(c)),
        ...filtered.filter(c => !isLinked(c)),
    ]

    return (
        <Modal open={open} onClose={onClose} title="Manage Categories">
            <input
                className="picker-modal__search"
                placeholder="Search categories…"
                value={search}
                onChange={e => setSearch(e.target.value)}
                autoFocus
            />
            {loading && <div className="picker-modal__loading">Loading…</div>}
            <div className="picker-modal__list">
                {sorted.map(cat => (
                    <label key={cat.id} className="picker-modal__item">
                        <input
                            type="checkbox"
                            checked={isLinked(cat)}
                            onChange={() => toggle(cat)}
                        />
                        <span className="picker-modal__name">{cat.name}</span>
                    </label>
                ))}
                {!loading && sorted.length === 0 && (
                    <div className="picker-modal__empty">No categories found</div>
                )}
            </div>
        </Modal>
    )
}
