import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { EmptyState } from '../EmptyState'

describe('EmptyState', () => {
    it('renders title', () => {
        render(<EmptyState title="No photos found" />)
        expect(screen.getByText('No photos found')).toBeInTheDocument()
    })

    it('renders description when provided', () => {
        render(<EmptyState title="No photos" description="Add some photos to get started" />)
        expect(screen.getByText('Add some photos to get started')).toBeInTheDocument()
    })

    it('renders CTA button when action provided', () => {
        render(<EmptyState title="No photos" action={{ label: 'Add folder', onClick: vi.fn() }} />)
        expect(screen.getByRole('button', { name: 'Add folder' })).toBeInTheDocument()
    })

    it('calls action.onClick when CTA clicked', async () => {
        const onClick = vi.fn()
        render(<EmptyState title="No photos" action={{ label: 'Add folder', onClick }} />)
        await userEvent.click(screen.getByRole('button', { name: 'Add folder' }))
        expect(onClick).toHaveBeenCalled()
    })

    it('does not render CTA when no action provided', () => {
        render(<EmptyState title="No photos" />)
        expect(screen.queryByRole('button')).not.toBeInTheDocument()
    })
})