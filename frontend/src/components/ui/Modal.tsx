import React, { useEffect } from 'react'
import './Modal.css'

interface ModalProps {
    open: boolean
    onClose: () => void
    title?: string
    children: React.ReactNode
}

export function Modal({ open, onClose, title, children }: ModalProps) {
    useEffect(() => {
        if (!open) return
        const handler = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose()
        }
        document.addEventListener('keydown', handler)
        return () => document.removeEventListener('keydown', handler)
    }, [open, onClose])

    if (!open) return null

    return (
        <div
            className="modal-backdrop"
            data-testid="modal-backdrop"
            onClick={onClose}
        >
            <div
                className="modal"
                onClick={(e) => e.stopPropagation()}
            >
                {title && <div className="modal__title">{title}</div>}
                <div className="modal__body">{children}</div>
            </div>
        </div>
    )
}