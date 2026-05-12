import React, { useEffect, useState, useCallback } from 'react'
import { Modal } from '@/components/ui/Modal'
import { getTemplateTags, linkPhotoTag, unlinkPhotoTag } from '@/api/client'
import type { TemplateTag, LinkedTag } from '@/api/client'
import './TagPickerModal.css'

interface Props {
    open: boolean
    photoId: number
    linkedTags: LinkedTag[]
    onClose: () => void
    onChanged: (linked: LinkedTag[]) => void
}

export function TagPickerModal({ open, photoId, linkedTags, onClose, onChanged }: Props) {
    const [all, setAll] = useState<TemplateTag[]>([])
    const [search, setSearch] = useState('')
    const [current, setCurrent] = useState<LinkedTag[]>(linkedTags)
    const [loading, setLoading] = useState(false)

    useEffect(() => { setCurrent(linkedTags) }, [linkedTags])

    const load = useCallback(async () => {
        setLoading(true)
        try {
            let skip = 0
            const pageSize = 50
            const result: TemplateTag[] = []
            while (true) {
                const page = await getTemplateTags(skip, pageSize)
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

    const isLinked = (tag: TemplateTag) => current.some(lt => lt.name === tag.name)

    async function toggle(tag: TemplateTag) {
        const linked = current.find(lt => lt.name === tag.name)
        if (linked) {
            await unlinkPhotoTag(photoId, linked.id)
            const next = current.filter(lt => lt.name !== tag.name)
            setCurrent(next)
            onChanged(next)
        } else {
            const lt = await linkPhotoTag(photoId, tag.name)
            const next = [...current, lt]
            setCurrent(next)
            onChanged(next)
        }
    }

    const filtered = all.filter(t =>
        t.name.toLowerCase().includes(search.toLowerCase())
    )
    const sorted = [
        ...filtered.filter(t => isLinked(t)),
        ...filtered.filter(t => !isLinked(t)),
    ]

    return (
        <Modal open={open} onClose={onClose} title="Manage Tags">
            <input
                className="picker-modal__search"
                placeholder="Search tags…"
                value={search}
                onChange={e => setSearch(e.target.value)}
                autoFocus
            />
            {loading && <div className="picker-modal__loading">Loading…</div>}
            <div className="picker-modal__list">
                {sorted.map(tag => (
                    <label key={tag.id} className="picker-modal__item">
                        <input
                            type="checkbox"
                            checked={isLinked(tag)}
                            onChange={() => toggle(tag)}
                        />
                        <span className="picker-modal__name">{tag.name}</span>
                    </label>
                ))}
                {!loading && sorted.length === 0 && (
                    <div className="picker-modal__empty">No tags found</div>
                )}
            </div>
        </Modal>
    )
}
