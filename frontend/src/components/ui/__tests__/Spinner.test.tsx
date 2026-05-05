import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Spinner } from '../Spinner'

describe('Spinner', () => {
    it('renders with data-testid', () => {
        render(<Spinner />)
        expect(screen.getByTestId('spinner')).toBeInTheDocument()
    })

    it('applies sm size class', () => {
        render(<Spinner size="sm" />)
        expect(screen.getByTestId('spinner')).toHaveClass('spinner--sm')
    })

    it('applies md size class by default', () => {
        render(<Spinner />)
        expect(screen.getByTestId('spinner')).toHaveClass('spinner--md')
    })

    it('applies lg size class', () => {
        render(<Spinner size="lg" />)
        expect(screen.getByTestId('spinner')).toHaveClass('spinner--lg')
    })
})