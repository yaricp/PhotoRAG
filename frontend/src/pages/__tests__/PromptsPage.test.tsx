import { describe, it, expect, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import i18n from '@/i18n'
import { PromptsPage } from '../PromptsPage'

vi.mock('@/api/base', () => ({ getBaseUrl: async () => 'http://localhost:8000' }))

afterEach(() => { i18n.changeLanguage('en') })

describe('PromptsPage i18n', () => {
    it('renders Russian prompts subtitle', async () => {
        i18n.changeLanguage('ru')
        render(<MemoryRouter><PromptsPage /></MemoryRouter>)
        expect(await screen.findByText(/Редактируйте промпты/)).toBeInTheDocument()
    })
})
