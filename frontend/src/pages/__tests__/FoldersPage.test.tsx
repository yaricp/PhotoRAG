import { describe, it, expect, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { server } from '@/test/server'
import { http, HttpResponse } from 'msw'
import i18n from '@/i18n'
import { FoldersPage } from '../FoldersPage'

vi.mock('@/api/base', () => ({ getBaseUrl: async () => 'http://localhost:8000' }))

afterEach(() => { i18n.changeLanguage('en') })

describe('FoldersPage i18n', () => {
    it('renders Russian folders UI', () => {
        i18n.changeLanguage('ru')
        render(<MemoryRouter><FoldersPage /></MemoryRouter>)
        expect(screen.getByRole('heading', { name: 'Наблюдатели' })).toBeInTheDocument()
    })

    it('localizes watcher status and shows a safe fallback for a missing timestamp', async () => {
        i18n.changeLanguage('ru')
        server.use(
            http.get('http://localhost:8000/api/watchers/', () => HttpResponse.json([
                { id: 8, path: '/photos/inbox', destination_path: '/photos/organized', status: 'active', updated_at: null },
            ])),
        )

        render(<MemoryRouter><FoldersPage /></MemoryRouter>)

        expect(await screen.findByText('Активен')).toBeInTheDocument()
        expect(screen.getByText(/Недоступно/)).toBeInTheDocument()
        expect(screen.queryByText(/Invalid Date/)).not.toBeInTheDocument()
    })

    it('localizes unknown watcher values and rejects an invalid timestamp', async () => {
        i18n.changeLanguage('es')
        server.use(
            http.get('http://localhost:8000/api/watchers/', () => HttpResponse.json([
                { id: 9, path: '/photos/inbox', destination_path: '/photos/organized', status: 'unexpected', updated_at: 'not-a-date' },
            ])),
        )

        render(<MemoryRouter><FoldersPage /></MemoryRouter>)

        expect(await screen.findByText('Desconocido')).toBeInTheDocument()
        expect(screen.getByText(/No disponible/)).toBeInTheDocument()
        expect(screen.queryByText(/Invalid Date/)).not.toBeInTheDocument()
    })
})
