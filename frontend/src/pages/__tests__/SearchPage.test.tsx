import { describe, it, expect, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import i18n from '@/i18n'
import { SearchPage } from '../SearchPage'

vi.mock('@/api/base', () => ({ getBaseUrl: async () => 'http://localhost:8000' }))

afterEach(() => { i18n.changeLanguage('en') })

describe('SearchPage i18n', () => {
    it('renders Russian title when language is ru', () => {
        i18n.changeLanguage('ru')
        render(<MemoryRouter><SearchPage /></MemoryRouter>)
        expect(screen.getByText('Семантический поиск')).toBeInTheDocument()
    })
})
