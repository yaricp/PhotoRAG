import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { server } from '@/test/server'
import { http, HttpResponse } from 'msw'
import { makeChatResponse, makePhoto } from '@/test/factories'
import { ChatPage } from '../ChatPage'

vi.mock('@/api/base', () => ({ getBaseUrl: async () => 'http://localhost:8000' }))

beforeAll(() => {
    // jsdom doesn't implement scrollIntoView
    window.HTMLElement.prototype.scrollIntoView = vi.fn()
})

const renderPage = () =>
    render(
        <MemoryRouter>
            <ChatPage />
        </MemoryRouter>
    )

describe('ChatPage', () => {
    it('renders the message input and send button', () => {
        renderPage()
        expect(screen.getByPlaceholderText(/ask something/i)).toBeInTheDocument()
        expect(screen.getByRole('button', { name: /send/i })).toBeInTheDocument()
    })

    it('renders the undo button', () => {
        renderPage()
        expect(screen.getByRole('button', { name: /undo/i })).toBeInTheDocument()
    })

    it('sends plain message when no photos selected', async () => {
        let capturedBody: any = null
        server.use(
            http.post('http://localhost:8000/api/chat/', async ({ request }) => {
                capturedBody = await request.json()
                return HttpResponse.json(makeChatResponse({ response: 'ok' }))
            })
        )
        renderPage()
        const textarea = screen.getByPlaceholderText(/ask something/i)
        fireEvent.change(textarea, { target: { value: 'Hello' } })
        fireEvent.click(screen.getByRole('button', { name: /send/i }))
        await waitFor(() => expect(screen.getByText('ok')).toBeInTheDocument())
        expect(capturedBody.message).toBe('Hello')
        expect(capturedBody.message).not.toContain('Selected photo IDs')
    })

    it('shows checkbox on context photo when photos arrive', async () => {
        const photo = makePhoto({ id: 99 })
        server.use(
            http.post('http://localhost:8000/api/chat/', () =>
                HttpResponse.json({ ...makeChatResponse(), photos: [photo] })
            )
        )
        renderPage()
        const textarea = screen.getByPlaceholderText(/ask something/i)
        fireEvent.change(textarea, { target: { value: 'find' } })
        fireEvent.click(screen.getByRole('button', { name: /send/i }))
        await waitFor(() =>
            expect(screen.getAllByRole('checkbox').length).toBeGreaterThan(1)
        )
    })

    it('undo button calls undo API and shows result', async () => {
        server.use(
            http.post('http://localhost:8000/api/history/undo/', () =>
                HttpResponse.json({ status: 'ok', detail: 'Undone: create_folder' })
            )
        )
        renderPage()
        fireEvent.click(screen.getByRole('button', { name: /undo/i }))
        await waitFor(() =>
            expect(screen.getByText(/Undone: create_folder/i)).toBeInTheDocument()
        )
    })
})
