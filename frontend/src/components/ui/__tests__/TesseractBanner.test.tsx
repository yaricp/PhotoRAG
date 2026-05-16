import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { TesseractBanner } from '../TesseractBanner'

const unavailableLocal = { available: false, ocr_mode: 'local' }
const availableLocal = { available: true, ocr_mode: 'local' }
const unavailableRemote = { available: false, ocr_mode: 'remote' }

beforeEach(() => {
    Object.defineProperty(navigator, 'clipboard', {
        value: { writeText: vi.fn().mockResolvedValue(undefined) },
        writable: true,
        configurable: true,
    })
})

describe('TesseractBanner', () => {
    it('renders when tesseract unavailable and OCR mode is local', () => {
        render(<TesseractBanner status={unavailableLocal} />)
        expect(screen.getByText(/tesseract ocr is not installed/i)).toBeInTheDocument()
    })

    it('hidden when tesseract is available', () => {
        render(<TesseractBanner status={availableLocal} />)
        expect(screen.queryByText(/tesseract ocr is not installed/i)).not.toBeInTheDocument()
    })

    it('hidden when OCR mode is remote, regardless of tesseract availability', () => {
        render(<TesseractBanner status={unavailableRemote} />)
        expect(screen.queryByText(/tesseract ocr is not installed/i)).not.toBeInTheDocument()
    })

    it('copy button calls clipboard with brew install command', async () => {
        render(<TesseractBanner status={unavailableLocal} />)
        fireEvent.click(screen.getByRole('button', { name: /copy/i }))
        expect(navigator.clipboard.writeText).toHaveBeenCalledWith('brew install tesseract')
    })
})
