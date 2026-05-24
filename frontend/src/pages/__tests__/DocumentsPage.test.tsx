import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import i18n from '@/i18n'
import { DocumentsPage } from '../DocumentsPage'

vi.mock('@/api/base', () => ({ getBaseUrl: async () => 'http://localhost:8000' }))

afterEach(() => { i18n.changeLanguage('en') })

describe('DocumentsPage i18n', () => {
    it('renders Russian documents title', () => {
        i18n.changeLanguage('ru')
        render(<MemoryRouter><DocumentsPage /></MemoryRouter>)
        expect(screen.getByText('Документы')).toBeInTheDocument()
    })
})
