import React from 'react'
import './Badge.css'

type BadgeVariant = 'default' | 'doc' | 'processing' | 'error' | 'success' | 'warning'

interface BadgeProps {
    variant?: BadgeVariant
    children: React.ReactNode
}

export function Badge({ variant = 'default', children }: BadgeProps) {
    return (
        <span className={`badge badge--${variant}`}>
            {children}
        </span>
    )
}