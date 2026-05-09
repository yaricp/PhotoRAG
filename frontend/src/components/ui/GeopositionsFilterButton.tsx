import React, { useEffect, useState } from 'react'
import { getGeopositions } from '@/api/client'
import { Modal } from './Modal'

interface Props {
    selectedGeo: number | null
    onSelect: (id: number | null) => void
}

export function GeopositionsFilterButton({ selectedGeo, onSelect }: Props) {
    const [open, setOpen] = useState(false)
    const [geos, setGeos] = useState<{ id: number; address: string | null }[]>([])

    useEffect(() => {
        getGeopositions().then(setGeos)
    }, [])

    const selected = geos.find(g => g.id === selectedGeo)
    const label = selected
        ? selected.address?.slice(0, 20) ?? `Location ${selected.id}`
        : 'Location'

    return (
        <>
            <button
                className={`filter-btn${selectedGeo !== null ? ' filter-btn--active' : ''}`}
                onClick={() => setOpen(true)}
            >
                {label}
            </button>

            <Modal open={open} onClose={() => setOpen(false)} title="Filter by Location">
                <div className="filter-modal__list">
                    <button
                        className={`filter-modal__item${selectedGeo === null ? ' filter-modal__item--active' : ''}`}
                        onClick={() => { onSelect(null); setOpen(false) }}
                    >
                        All locations
                    </button>
                    {geos.map(geo => (
                        <button
                            key={geo.id}
                            className={`filter-modal__item${selectedGeo === geo.id ? ' filter-modal__item--active' : ''}`}
                            onClick={() => { onSelect(geo.id); setOpen(false) }}
                        >
                            {geo.address ?? `Location ${geo.id}`}
                        </button>
                    ))}
                </div>
            </Modal>
        </>
    )
}
