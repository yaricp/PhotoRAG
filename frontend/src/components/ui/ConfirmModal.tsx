import React from 'react'
import { Modal } from './Modal'
import './ConfirmModal.css'

interface ConfirmModalProps {
    open: boolean
    title: string
    message?: string
    confirmLabel?: string
    variant?: 'danger' | 'warning'
    onConfirm: () => void
    onClose: () => void
}

export function ConfirmModal({
    open,
    title,
    message,
    confirmLabel = 'Confirm',
    variant = 'danger',
    onConfirm,
    onClose,
}: ConfirmModalProps) {
    return (
        <Modal open={open} onClose={onClose} title={title}>
            {message && <p className="confirm-modal__message">{message}</p>}
            <div className="confirm-modal__actions">
                <button className="confirm-modal__btn confirm-modal__btn--cancel" onClick={onClose}>
                    Cancel
                </button>
                <button
                    className={`confirm-modal__btn confirm-modal__btn--confirm confirm-modal__btn--${variant}`}
                    onClick={() => { onConfirm(); onClose() }}
                >
                    {confirmLabel}
                </button>
            </div>
        </Modal>
    )
}
