import { describe, it, expect, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import i18n from '@/i18n'
import { ModelsPage } from '../ModelsPage'

vi.mock('@/api/base', () => ({ getBaseUrl: async () => 'http://localhost:8000' }))

afterEach(() => { i18n.changeLanguage('en') })

describe('ModelsPage i18n', () => {
    it('renders Russian models description', async () => {
        i18n.changeLanguage('ru')
        render(<MemoryRouter><ModelsPage /></MemoryRouter>)
        expect(await screen.findByText(/Настройте модели/)).toBeInTheDocument()
    })
})
