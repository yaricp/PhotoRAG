import React from 'react'
import { Button } from './Button'
import './EmptyState.css'

interface EmptyStateProps {
    title: string
    description?: string
    action?: { label: string; onClick: () => void }
}

export function EmptyState({ title, description, action }: EmptyStateProps) {
    return (
        <div className="empty-state">
            <p className="empty-state__title">{title}</p>
            {description && (
                <p className="empty-state__description">{description}</p>
            )}
            {action && (
                <Button variant="ghost" onClick={action.onClick}>
                    {action.label}
                </Button>
            )}
        </div>
    )
}