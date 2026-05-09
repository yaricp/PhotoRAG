import React, { useEffect, useState } from 'react'
import { getTags } from '@/api/client'
import { Modal } from './Modal'

interface Props {
    selectedTags: number[]
    onToggle: (id: number) => void
}

export function TagsFilterButton({ selectedTags, onToggle }: Props) {
    const [open, setOpen] = useState(false)
    const [tags, setTags] = useState<{ id: number; name: string }[]>([])

    useEffect(() => {
        getTags().then(setTags)
    }, [])

    const label = selectedTags.length ? `Tags (${selectedTags.length})` : 'Tags'

    return (
        <>
            <button
                className={`filter-btn${selectedTags.length ? ' filter-btn--active' : ''}`}
                onClick={() => setOpen(true)}
            >
                {label}
            </button>

            <Modal open={open} onClose={() => setOpen(false)} title="Filter by Tags">
                <div className="filter-modal__list">
                    {tags.map(tag => (
                        <button
                            key={tag.id}
                            className={`filter-modal__item${selectedTags.includes(tag.id) ? ' filter-modal__item--active' : ''}`}
                            onClick={() => { onToggle(tag.id); setOpen(false) }}
                        >
                            {tag.name}
                        </button>
                    ))}
                </div>
            </Modal>
        </>
    )
}
