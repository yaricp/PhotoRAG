import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { server } from '@/test/server'
import { http, HttpResponse } from 'msw'
import i18n from '@/i18n'
import App from '../App'

vi.mock('@/api/base', () => ({ getBaseUrl: async () => 'http://localhost:8000' }))

afterEach(async () => { await i18n.changeLanguage('en') })

describe('App', () => {
    it('renders sidebar', () => {
        render(
            <MemoryRouter>
                <App />
            </MemoryRouter>
        )
        expect(screen.getByTestId('sidebar')).toBeInTheDocument()
    })

    it('renders main content area', () => {
        render(
            <MemoryRouter>
                <App />
            </MemoryRouter>
        )
        expect(screen.getByTestId('main-content')).toBeInTheDocument()
    })

    it('renders gallery page by default', () => {
        render(
            <MemoryRouter initialEntries={['/']}>
                <App />
            </MemoryRouter>
        )
        expect(screen.getByTestId('page-gallery')).toBeInTheDocument()
    })

    it('syncs i18n language from saved settings on mount', async () => {
        server.use(
            http.get('http://localhost:8000/api/settings/', () =>
                HttpResponse.json({ default_language: 'ru', default_folder: '' })
            )
        )
        render(<MemoryRouter><App /></MemoryRouter>)
        await waitFor(() => expect(i18n.language).toBe('ru'))
    })
})