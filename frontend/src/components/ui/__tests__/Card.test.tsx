import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Card } from '../Card'

describe('Card', () => {
    it('renders children', () => {
        render(<Card>content</Card>)
        expect(screen.getByText('content')).toBeInTheDocument()
    })

    it('has card class', () => {
        render(<Card>content</Card>)
        expect(screen.getByText('content').closest('.card')).toBeInTheDocument()
    })

    it('passes className prop', () => {
        render(<Card className="extra">content</Card>)
        const el = screen.getByText('content').closest('.card')
        expect(el).toHaveClass('extra')
    })

    it('forwards onClick', async () => {
        const { default: userEvent } = await import('@testing-library/user-event')
        const onClick = vi.fn()
        render(<Card onClick={onClick}>click me</Card>)
        await userEvent.click(screen.getByText('click me'))
        expect(onClick).toHaveBeenCalled()
    })
})