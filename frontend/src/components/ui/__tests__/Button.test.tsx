import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Button } from '../Button'

describe('Button', () => {
    it('renders children', () => {
        render(<Button>Click me</Button>)
        expect(screen.getByText('Click me')).toBeInTheDocument()
    })

    it('calls onClick when clicked', async () => {
        const onClick = vi.fn()
        render(<Button onClick={onClick}>Click</Button>)
        await userEvent.click(screen.getByRole('button'))
        expect(onClick).toHaveBeenCalledTimes(1)
    })

    it('is disabled when disabled prop passed', () => {
        render(<Button disabled>Click</Button>)
        expect(screen.getByRole('button')).toBeDisabled()
    })

    it('does not call onClick when disabled', async () => {
        const onClick = vi.fn()
        render(<Button disabled onClick={onClick}>Click</Button>)
        await userEvent.click(screen.getByRole('button'))
        expect(onClick).not.toHaveBeenCalled()
    })

    it('shows spinner when loading', () => {
        render(<Button loading>Click</Button>)
        expect(screen.getByTestId('spinner')).toBeInTheDocument()
    })

    it('is disabled when loading', () => {
        render(<Button loading>Click</Button>)
        expect(screen.getByRole('button')).toBeDisabled()
    })

    it('applies primary variant class by default', () => {
        render(<Button>Click</Button>)
        expect(screen.getByRole('button')).toHaveClass('btn--primary')
    })

    it('applies ghost variant class', () => {
        render(<Button variant="ghost">Click</Button>)
        expect(screen.getByRole('button')).toHaveClass('btn--ghost')
    })

    it('applies danger variant class', () => {
        render(<Button variant="danger">Click</Button>)
        expect(screen.getByRole('button')).toHaveClass('btn--danger')
    })
})