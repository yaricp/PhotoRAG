import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Modal } from '../Modal'

describe('Modal', () => {
    it('renders when open=true', () => {
        render(<Modal open onClose={vi.fn()}>content</Modal>)
        expect(screen.getByText('content')).toBeInTheDocument()
    })

    it('does not render when open=false', () => {
        render(<Modal open={false} onClose={vi.fn()}>content</Modal>)
        expect(screen.queryByText('content')).not.toBeInTheDocument()
    })

    it('calls onClose when Escape pressed', async () => {
        const onClose = vi.fn()
        render(<Modal open onClose={onClose}>content</Modal>)
        await userEvent.keyboard('{Escape}')
        expect(onClose).toHaveBeenCalledTimes(1)
    })

    it('calls onClose when backdrop clicked', async () => {
        const onClose = vi.fn()
        render(<Modal open onClose={onClose}>content</Modal>)
        await userEvent.click(screen.getByTestId('modal-backdrop'))
        expect(onClose).toHaveBeenCalledTimes(1)
    })

    it('does not close when modal content clicked', async () => {
        const onClose = vi.fn()
        render(<Modal open onClose={onClose}>content</Modal>)
        await userEvent.click(screen.getByText('content'))
        expect(onClose).not.toHaveBeenCalled()
    })

    it('renders title when provided', () => {
        render(<Modal open onClose={vi.fn()} title="Confirm">content</Modal>)
        expect(screen.getByText('Confirm')).toBeInTheDocument()
    })
})