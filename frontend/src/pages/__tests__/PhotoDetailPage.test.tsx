import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { server } from '@/test/server'
import { http, HttpResponse } from 'msw'
import { makePhoto } from '@/test/factories'
import { PhotoDetailPage } from '../PhotoDetailPage'

vi.mock('@/api/base', () => ({ getBaseUrl: async () => 'http://localhost:8000' }))

const renderDetail = (id = '1') =>
    render(
        <MemoryRouter initialEntries={[`/photo/${id}`]}>
            <Routes>
                <Route path="/photo/:id" element={<PhotoDetailPage />} />
                <Route path="/" element={<div data-testid="gallery-page" />} />
            </Routes>
        </MemoryRouter>
    )

describe('PhotoDetailPage', () => {
    it('shows spinner while loading', () => {
        renderDetail()
        expect(screen.getByTestId('spinner')).toBeInTheDocument()
    })

    it('renders photo description after load', async () => {
        server.use(
            http.get('http://localhost:8000/api/photos/:id', () =>
                HttpResponse.json(makePhoto({ description: 'A beautiful sunset' }))
            )
        )
        renderDetail()
        await waitFor(() =>
            expect(screen.getByText('A beautiful sunset')).toBeInTheDocument()
        )
    })

    it('renders tags with confidence percentage', async () => {
        server.use(
            http.get('http://localhost:8000/api/photos/:id', () =>
                HttpResponse.json(makePhoto({
                    tags: [{ tag: { id: 1, name: 'landscape' }, confidence_score: 0.92 }]
                }))
            )
        )
        renderDetail()
        await waitFor(() => {
            expect(screen.getByText('landscape')).toBeInTheDocument()
            expect(screen.getByText('92%')).toBeInTheDocument()
        })
    })

    it('shows OCR panel only when is_doc=true', async () => {
        server.use(
            http.get('http://localhost:8000/api/photos/:id', () =>
                HttpResponse.json(makePhoto({ is_doc: true, ocr_text: 'Invoice #1234' }))
            )
        )
        renderDetail()
        await waitFor(() =>
            expect(screen.getByText('Invoice #1234')).toBeInTheDocument()
        )
    })

    it('does not show OCR panel when is_doc=false', async () => {
        server.use(
            http.get('http://localhost:8000/api/photos/:id', () =>
                HttpResponse.json(makePhoto({ is_doc: false, ocr_text: null }))
            )
        )
        renderDetail()
        await waitFor(() => screen.getByTestId('photo-detail'))
        expect(screen.queryByTestId('ocr-panel')).not.toBeInTheDocument()
    })

    it('shows delete confirmation modal on delete click', async () => {
        server.use(
            http.get('http://localhost:8000/api/photos/:id', () =>
                HttpResponse.json(makePhoto())
            )
        )
        renderDetail()
        await waitFor(() => screen.getByTestId('photo-detail'))
        await userEvent.click(screen.getByRole('button', { name: /delete/i }))
        expect(screen.getByText(/are you sure/i)).toBeInTheDocument()
    })

    it('calls DELETE and navigates to / on confirm', async () => {
        let deleted = false
        server.use(
            http.get('http://localhost:8000/api/photos/:id', () =>
                HttpResponse.json(makePhoto({ id: 1 }))
            ),
            http.delete('http://localhost:8000/api/photos/:id', () => {
                deleted = true
                return HttpResponse.json(makePhoto({ id: 1 }))
            })
        )
        renderDetail('1')
        await waitFor(() => screen.getByTestId('photo-detail'))
        await userEvent.click(screen.getByRole('button', { name: /delete/i }))
        await userEvent.click(screen.getByRole('button', { name: /confirm/i }))
        await waitFor(() => {
            expect(deleted).toBe(true)
            expect(screen.getByTestId('gallery-page')).toBeInTheDocument()
        })
    })

    it('shows camera info when available', async () => {
        server.use(
            http.get('http://localhost:8000/api/photos/:id', () =>
                HttpResponse.json(makePhoto({
                    camera: { id: 1, make: 'Sony', model: 'A7III' }
                }))
            )
        )
        renderDetail()
        await waitFor(() =>
            expect(screen.getByText('Sony A7III')).toBeInTheDocument()
        )
    })
})