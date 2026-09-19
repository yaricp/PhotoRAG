import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/server'
import { makePhoto } from '@/test/factories'
import { MemoryRouter } from 'react-router-dom'
import i18n from '@/i18n'
import { SearchPage } from '../SearchPage'

vi.mock('@/api/base', () => ({ getBaseUrl: async () => 'http://localhost:8000' }))

afterEach(() => { i18n.changeLanguage('en') })

describe('SearchPage i18n', () => {
    it('uses thumbnails for search result images', async () => {
        server.use(
            http.post('http://localhost:8000/api/search/', () =>
                HttpResponse.json([{ photo: makePhoto({ id: 11 }), distance: 0.12 }])
            )
        )
        render(<MemoryRouter><SearchPage /></MemoryRouter>)
        await userEvent.type(screen.getByPlaceholderText(/search your photos/i), 'cat')
        await userEvent.click(screen.getByRole('button', { name: /search/i }))
        await waitFor(() => expect(screen.getByRole('img')).toBeInTheDocument())
        const img = screen.getByRole('img')
        expect(img.getAttribute('src')).toContain('thumbnail=1')
        expect(img.getAttribute('src')).toContain('width=360')
        expect(img.getAttribute('src')).toContain('height=270')
    })

    it('renders Russian UI when language is ru', () => {
        i18n.changeLanguage('ru')
        render(<MemoryRouter><SearchPage /></MemoryRouter>)
        expect(screen.getByPlaceholderText('Поиск по фотографиям…')).toBeInTheDocument()
    })
})
