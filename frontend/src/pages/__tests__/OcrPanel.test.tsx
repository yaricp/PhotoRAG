import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { OcrPanel } from '../OcrPanel'

describe('OcrPanel', () => {
    it('renders ocr text', () => {
        render(<OcrPanel text="Invoice #1234\nTotal: $500" />)
        expect(screen.getByText(/Invoice #1234/)).toBeInTheDocument()
    })

    it('shows copy button', () => {
        render(<OcrPanel text="some text" />)
        expect(screen.getByRole('button', { name: /copy/i })).toBeInTheDocument()
    })

    it('copies text to clipboard on button click', async () => {
        const writeText = vi.fn().mockResolvedValue(undefined)
        Object.assign(navigator, { clipboard: { writeText } })

        render(<OcrPanel text="Invoice #1234" />)
        await userEvent.click(screen.getByRole('button', { name: /copy/i }))
        expect(writeText).toHaveBeenCalledWith('Invoice #1234')
    })

    it('shows copied confirmation after copy', async () => {
        const writeText = vi.fn().mockResolvedValue(undefined)
        Object.assign(navigator, { clipboard: { writeText } })

        render(<OcrPanel text="Invoice #1234" />)
        await userEvent.click(screen.getByRole('button', { name: /copy/i }))
        expect(screen.getByRole('button', { name: /copied/i })).toBeInTheDocument()
    })

    it('has data-testid ocr-panel', () => {
        render(<OcrPanel text="text" />)
        expect(screen.getByTestId('ocr-panel')).toBeInTheDocument()
    })
})