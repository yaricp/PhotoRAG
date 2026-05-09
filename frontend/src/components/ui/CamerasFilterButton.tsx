import React, { useEffect, useState } from 'react'
import { getCameras } from '@/api/client'
import { Modal } from './Modal'

interface Props {
    selectedCamera: number | null
    onSelect: (id: number | null) => void
}

export function CamerasFilterButton({ selectedCamera, onSelect }: Props) {
    const [open, setOpen] = useState(false)
    const [cameras, setCameras] = useState<{ id: number; make: string | null; model: string | null }[]>([])

    useEffect(() => {
        getCameras().then(setCameras)
    }, [])

    const selected = cameras.find(c => c.id === selectedCamera)
    const label = selected
        ? `${selected.make ?? ''} ${selected.model ?? ''}`.trim() || `Camera ${selected.id}`
        : 'Camera'

    return (
        <>
            <button
                className={`filter-btn${selectedCamera !== null ? ' filter-btn--active' : ''}`}
                onClick={() => setOpen(true)}
            >
                {label}
            </button>

            <Modal open={open} onClose={() => setOpen(false)} title="Filter by Camera">
                <div className="filter-modal__list">
                    <button
                        className={`filter-modal__item${selectedCamera === null ? ' filter-modal__item--active' : ''}`}
                        onClick={() => { onSelect(null); setOpen(false) }}
                    >
                        All cameras
                    </button>
                    {cameras.map(cam => (
                        <button
                            key={cam.id}
                            className={`filter-modal__item${selectedCamera === cam.id ? ' filter-modal__item--active' : ''}`}
                            onClick={() => { onSelect(cam.id); setOpen(false) }}
                        >
                            {`${cam.make ?? ''} ${cam.model ?? ''}`.trim() || `Camera ${cam.id}`}
                        </button>
                    ))}
                </div>
            </Modal>
        </>
    )
}
