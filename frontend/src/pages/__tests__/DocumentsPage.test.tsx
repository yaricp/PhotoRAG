import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/server'
import { makePaginatedPhotos, makePhoto } from '@/test/factories'
import i18n from '@/i18n'
import { DocumentsPage } from '../DocumentsPage'

vi.mock('@/api/base', () => ({ getBaseUrl: async () => 'http://localhost:8000' }))

afterEach(() => { i18n.changeLanguage('en') })

describe('DocumentsPage i18n', () => {
    it('uses thumbnails for document card images', async () => {
        server.use(
            http.get('http://localhost:8000/api/photos/', () =>
                HttpResponse.json(makePaginatedPhotos([makePhoto({ id: 7, is_doc: true })]))
            )
        )
        render(<MemoryRouter><DocumentsPage /></MemoryRouter>)
        const img = await screen.findByRole('img')
        expect(img.getAttribute('src')).toContain('thumbnail=1')
        expect(img.getAttribute('src')).toContain('width=360')
        expect(img.getAttribute('src')).toContain('height=270')
    })

    it('renders Russian empty state when no documents', async () => {
        server.use(
            http.get('http://localhost:8000/api/photos', () =>
                HttpResponse.json({ items: [], total: 0 })
            )
        )
        i18n.changeLanguage('ru')
        render(<MemoryRouter><DocumentsPage /></MemoryRouter>)
        expect(await screen.findByText('Нет документов')).toBeInTheDocument()
    })
})
