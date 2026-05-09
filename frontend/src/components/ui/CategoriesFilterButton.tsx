import React, { useEffect, useState } from 'react'
import { getCategories } from '@/api/client'
import { Modal } from './Modal'

interface Props {
    selectedCategories: number[]
    onToggle: (id: number) => void
}

export function CategoriesFilterButton({ selectedCategories, onToggle }: Props) {
    const [open, setOpen] = useState(false)
    const [categories, setCategories] = useState<{ id: number; name: string }[]>([])

    useEffect(() => {
        getCategories().then(setCategories)
    }, [])

    const label = selectedCategories.length ? `Categories (${selectedCategories.length})` : 'Categories'

    return (
        <>
            <button
                className={`filter-btn${selectedCategories.length ? ' filter-btn--active' : ''}`}
                onClick={() => setOpen(true)}
            >
                {label}
            </button>

            <Modal open={open} onClose={() => setOpen(false)} title="Filter by Categories">
                <div className="filter-modal__list">
                    {categories.map(cat => (
                        <button
                            key={cat.id}
                            className={`filter-modal__item${selectedCategories.includes(cat.id) ? ' filter-modal__item--active' : ''}`}
                            onClick={() => { onToggle(cat.id); setOpen(false) }}
                        >
                            {cat.name}
                        </button>
                    ))}
                </div>
            </Modal>
        </>
    )
}
