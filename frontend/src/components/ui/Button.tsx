import React from 'react'
import { Spinner } from './Spinner'
import './Button.css'

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
    variant?: 'primary' | 'ghost' | 'danger'
    loading?: boolean
}

export function Button({
    variant = 'primary',
    loading = false,
    disabled,
    children,
    className = '',
    ...props
}: ButtonProps) {
    return (
        <button
            className={`btn btn--${variant} ${className}`}
            disabled={disabled || loading}
            {...props}
        >
            {loading ? <Spinner size="sm" /> : children}
        </button>
    )
}