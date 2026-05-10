import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { server } from '@/test/server'
import { http, HttpResponse } from 'msw'
import { SettingsPage } from '../SettingsPage'

vi.mock('@/api/base', () => ({ getBaseUrl: async () => 'http://localhost:8000' }))

const renderPage = () =>
    render(
        <MemoryRouter>
            <SettingsPage />
        </MemoryRouter>
    )

describe('SettingsPage', () => {
    it('renders default folder input', () => {
        renderPage()
        expect(screen.getByLabelText(/default folder/i)).toBeInTheDocument()
    })

    it('loads existing value from API', async () => {
        server.use(
            http.get('http://localhost:8000/api/settings/', () =>
                HttpResponse.json({ default_folder: '/my/photos', default_language: 'en' })
            )
        )
        renderPage()
        await waitFor(() => {
            const input = screen.getByLabelText(/default folder/i) as HTMLInputElement
            expect(input.value).toBe('/my/photos')
        })
    })

    it('calls updateSetting when Save is clicked', async () => {
        let folderBody: string | null = null
        server.use(
            http.put('http://localhost:8000/api/settings/:key', async ({ request, params }) => {
                const body = await request.text()
                if (params.key === 'default_folder') folderBody = body
                return HttpResponse.json({ key: params.key, value: '' })
            })
        )
        renderPage()
        await waitFor(() => screen.getByRole('button', { name: /save/i }))
        const input = screen.getByLabelText(/default folder/i)
        fireEvent.change(input, { target: { value: '/new' } })
        fireEvent.click(screen.getByRole('button', { name: /save/i }))
        await waitFor(() => expect(folderBody).toContain('/new'))
    })
})
