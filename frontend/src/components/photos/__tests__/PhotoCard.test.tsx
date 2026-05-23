import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { PhotoCard } from '../PhotoCard'
import { makePhoto, makePhotoTag, makeJob } from '@/test/factories'

const renderCard = (photo = makePhoto()) =>
    render(
        <MemoryRouter>
            <PhotoCard photo={photo} />
        </MemoryRouter>
    )

describe('PhotoCard', () => {
    it('renders photo filename', () => {
        renderCard(makePhoto({ file_path: '/photos/sunset.png' }))
        expect(screen.getByText('sunset.png')).toBeInTheDocument()
    })

    it('img src uses /api/static in browser (no electronAPI)', () => {
        const photo = makePhoto({ file_path: '/photos/img.png' })
        renderCard(photo)
        const img = screen.getByRole('img')
        expect(img.getAttribute('src')).toContain('/api/static')
    })

    it('shows Document badge when is_doc=true', () => {
        renderCard(makePhoto({ is_doc: true }))
        expect(screen.getByText('Document')).toBeInTheDocument()
    })

    it('does not show Document badge when is_doc=false', () => {
        renderCard(makePhoto({ is_doc: false }))
        expect(screen.queryByText('Document')).not.toBeInTheDocument()
    })

    it('shows top tag name', () => {
        const photo = makePhoto({
            tags_rel: [makePhotoTag({ tag: { id: 1, name: 'invoice' }, confidence_score: 0.95 })]
        })
        renderCard(photo)
        expect(screen.getByText('invoice')).toBeInTheDocument()
    })

    it('shows Processing badge when job prop provided', () => {
        const photo = makePhoto()
        const job = makeJob({ status: 'processing' })
        render(
            <MemoryRouter>
                <PhotoCard photo={photo} job={job} />
            </MemoryRouter>
        )
        expect(screen.getByText('Processing…')).toBeInTheDocument()
    })

    it('navigates to /photo/:id on click', async () => {
        let pathname = ''
        const { default: userEvent } = await import('@testing-library/user-event')
        const { render: r } = await import('@testing-library/react')
        const { MemoryRouter: MR, Route, Routes, useLocation } = await import('react-router-dom')

        function LocationCapture() {
            const loc = useLocation()
            pathname = loc.pathname
            return null
        }

        const photo = makePhoto({ id: 7 })
        r(
            <MR initialEntries={['/']}>
                <Routes>
                    <Route path="/" element={<><PhotoCard photo={photo} /><LocationCapture /></>} />
                    <Route path="/photo/:id" element={<LocationCapture />} />
                </Routes>
            </MR>
        )

        await userEvent.click(screen.getByRole('article'))
        expect(pathname).toBe('/photo/7')
    })
})

describe('PhotoCard action buttons', () => {
    it('shows no action buttons when no handlers provided', () => {
        render(<MemoryRouter><PhotoCard photo={makePhoto()} /></MemoryRouter>)
        expect(screen.queryByRole('button', { name: /archive/i })).toBeNull()
        expect(screen.queryByRole('button', { name: /delete/i })).toBeNull()
    })

    it('shows Archive button when onArchive provided', () => {
        render(<MemoryRouter><PhotoCard photo={makePhoto()} onArchive={vi.fn()} /></MemoryRouter>)
        expect(screen.getByRole('button', { name: /archive/i })).toBeInTheDocument()
    })

    it('shows Delete button when onDelete provided', () => {
        render(<MemoryRouter><PhotoCard photo={makePhoto()} onDelete={vi.fn()} /></MemoryRouter>)
        expect(screen.getByRole('button', { name: /delete/i })).toBeInTheDocument()
    })

    it('calls onArchive when Archive button clicked', () => {
        const onArchive = vi.fn()
        render(<MemoryRouter><PhotoCard photo={makePhoto()} onArchive={onArchive} /></MemoryRouter>)
        fireEvent.click(screen.getByRole('button', { name: /archive/i }))
        expect(onArchive).toHaveBeenCalledOnce()
    })

    it('calls onDelete when Delete button clicked', () => {
        const onDelete = vi.fn()
        render(<MemoryRouter><PhotoCard photo={makePhoto()} onDelete={onDelete} /></MemoryRouter>)
        fireEvent.click(screen.getByRole('button', { name: /delete/i }))
        expect(onDelete).toHaveBeenCalledOnce()
    })
})