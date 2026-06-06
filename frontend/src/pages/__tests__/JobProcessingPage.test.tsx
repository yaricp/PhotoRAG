import { describe, it, expect, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import i18n from '@/i18n'
import { JobProcessingPage } from '../JobProcessingPage'

vi.mock('@/api/base', () => ({ getBaseUrl: async () => 'http://localhost:8000' }))

afterEach(() => { i18n.changeLanguage('en') })

describe('JobProcessingPage i18n', () => {
    it('renders Russian processing UI', async () => {
        i18n.changeLanguage('ru')
        render(<MemoryRouter><JobProcessingPage /></MemoryRouter>)
        expect(await screen.findByText('Нет активной обработки')).toBeInTheDocument()
    })
})
