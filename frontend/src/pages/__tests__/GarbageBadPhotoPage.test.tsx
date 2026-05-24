import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { server } from '@/test/server'
import { http, HttpResponse } from 'msw'
import { makePaginatedPhotos, makePhoto } from '@/test/factories'
import i18n from '@/i18n'
import { GarbageBadPhotoPage } from '../GarbageBadPhotoPage'

vi.mock('@/api/base', () => ({ getBaseUrl: async () => 'http://localhost:8000' }))

afterEach(() => { i18n.changeLanguage('en') })

const renderPage = () =>
    render(
        <MemoryRouter>
            <GarbageBadPhotoPage />
        </MemoryRouter>
    )

function mockSummary(counts: Record<string, number>) {
    server.use(
        http.get('http://localhost:8000/api/garbage/', () =>
            HttpResponse.json({ counts })
        )
    )
}

function mockPhotos(issueType: string, photos = [makePhoto()]) {
    server.use(
        http.get(`http://localhost:8000/api/garbage/${issueType}/photos/`, () =>
            HttpResponse.json(makePaginatedPhotos(photos))
        )
    )
}

describe('GarbageBadPhotoPage', () => {
    it('renders the page title', async () => {
        mockSummary({})
        renderPage()
        await waitFor(() =>
            expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument()
        )
    })

    it('shows four category sections', async () => {
        mockSummary({})
        renderPage()
        await waitFor(() => {
            expect(screen.getByText(/Technical Garbage/i)).toBeInTheDocument()
            expect(screen.getByText(/Semantic Garbage/i)).toBeInTheDocument()
            expect(screen.getByText(/Temporary Garbage/i)).toBeInTheDocument()
            expect(screen.getByText(/Subjective Garbage/i)).toBeInTheDocument()
        })
    })

    it('shows blur count badge when summary has blur data', async () => {
        mockSummary({ blur: 5 })
        renderPage()
        await waitFor(() => expect(screen.getByText('5')).toBeInTheDocument())
    })

    it('expands blur row and shows photo cards', async () => {
        mockSummary({ blur: 1 })
        mockPhotos('blur')
        renderPage()
        await waitFor(() => screen.getByText('1'))
        fireEvent.click(screen.getByText(/Blurry/i))
        await waitFor(() =>
            expect(screen.getAllByRole('article')).toHaveLength(1)
        )
    })

    it('shows placeholder text for semantic, temporary, subjective sections', async () => {
        mockSummary({})
        renderPage()
        await waitFor(() =>
            expect(screen.getAllByText(/Coming soon/i).length).toBeGreaterThanOrEqual(3)
        )
    })

    it('renders Russian garbage title', async () => {
        mockSummary({})
        i18n.changeLanguage('ru')
        render(<MemoryRouter><GarbageBadPhotoPage /></MemoryRouter>)
        await waitFor(() =>
            expect(screen.getByRole('heading', { name: 'Мусор' })).toBeInTheDocument()
        )
    })
})
