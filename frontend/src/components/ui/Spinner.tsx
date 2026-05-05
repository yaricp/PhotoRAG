import React from 'react'
import './Spinner.css'

interface SpinnerProps {
    size?: 'sm' | 'md' | 'lg'
}

export function Spinner({ size = 'md' }: SpinnerProps) {
    return (
        <span
            data-testid="spinner"
            className={`spinner spinner--${size}`}
            aria-label="Loading"
        />
    )
}