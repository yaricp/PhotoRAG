import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { server } from '@/test/server'
import { http, HttpResponse } from 'msw'
import { makePaginatedPhotos, makePhoto } from '@/test/factories'
import { GalleryPage } from '../GalleryPage'

vi.mock('@/api/base', () => ({ getBaseUrl: async () => 'http://localhost:8000' }))

const renderGallery = () =>
    render(
        <MemoryRouter>
            <GalleryPage />
        </MemoryRouter>
    )

describe('GalleryPage', () => {
    it('shows loading state initially', () => {
        renderGallery()
        expect(screen.getByTestId('spinner')).toBeInTheDocument()
    })

    it('renders photo cards after fetch', async () => {
        renderGallery()
        await waitFor(() =>
            expect(screen.getAllByRole('article')).toHaveLength(3)
        )
    })

    it('shows empty state when no photos', async () => {
        server.use(
            http.get('http://localhost:8000/api/photos/', () =>
                HttpResponse.json(makePaginatedPhotos([]))
            )
        )
        renderGallery()
        await waitFor(() =>
            expect(screen.getByText(/no photos/i)).toBeInTheDocument()
        )
    })

    it('shows error state on fetch failure', async () => {
        server.use(
            http.get('http://localhost:8000/api/photos/', () =>
                new HttpResponse(null, { status: 500 })
            )
        )
        renderGallery()
        await waitFor(() =>
            expect(screen.getByText(/error/i)).toBeInTheDocument()
        )
    })

    it('filters by is_doc when Documents filter clicked', async () => {
        let capturedUrl = ''
        server.use(
            http.get('http://localhost:8000/api/photos/', ({ request }) => {
                capturedUrl = request.url
                return HttpResponse.json(makePaginatedPhotos([makePhoto({ is_doc: true })]))
            })
        )
        renderGallery()
        await waitFor(() => screen.getAllByRole('article'))
        await userEvent.click(screen.getByRole('button', { name: /documents only/i }))
        await waitFor(() => expect(capturedUrl).toContain('is_doc=true'))
    })
})