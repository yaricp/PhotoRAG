import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Badge } from '../Badge'

describe('Badge', () => {
    it('renders label', () => {
        render(<Badge>document</Badge>)
        expect(screen.getByText('document')).toBeInTheDocument()
    })

    it('applies default variant', () => {
        render(<Badge>tag</Badge>)
        expect(screen.getByText('tag')).toHaveClass('badge--default')
    })

    it('applies doc variant', () => {
        render(<Badge variant="doc">doc</Badge>)
        expect(screen.getByText('doc')).toHaveClass('badge--doc')
    })

    it('applies processing variant', () => {
        render(<Badge variant="processing">processing</Badge>)
        expect(screen.getByText('processing')).toHaveClass('badge--processing')
    })

    it('applies error variant', () => {
        render(<Badge variant="error">error</Badge>)
        expect(screen.getByText('error')).toHaveClass('badge--error')
    })

    it('applies success variant', () => {
        render(<Badge variant="success">done</Badge>)
        expect(screen.getByText('done')).toHaveClass('badge--success')
    })
})