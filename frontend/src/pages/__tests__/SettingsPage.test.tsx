import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { server } from '@/test/server'
import { http, HttpResponse } from 'msw'
import { SettingsPage } from '../SettingsPage'
import i18n from '@/i18n'

vi.mock('@/api/base', () => ({ getBaseUrl: async () => 'http://localhost:8000' }))

afterEach(async () => { await i18n.changeLanguage('en') })

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

    it('renders Russian settings labels when language is ru', () => {
        i18n.changeLanguage('ru')
        render(<MemoryRouter><SettingsPage /></MemoryRouter>)
        expect(screen.getByText('Язык по умолчанию')).toBeInTheDocument()
    })

    it('syncs i18n language when saved setting is ru', async () => {
        server.use(
            http.get('http://localhost:8000/api/settings/', () =>
                HttpResponse.json({ default_language: 'ru', default_folder: '' })
            )
        )
        render(<MemoryRouter><SettingsPage /></MemoryRouter>)
        await waitFor(() => expect(i18n.language).toBe('ru'))
    })

    it('applies language change immediately even when DB save fails', async () => {
        server.use(
            http.get('http://localhost:8000/api/settings/', () =>
                HttpResponse.json({ default_language: 'en', default_folder: '' })
            ),
            http.put('http://localhost:8000/api/settings/:key', () =>
                HttpResponse.json({ error: 'database is locked' }, { status: 500 })
            )
        )
        render(<MemoryRouter><SettingsPage /></MemoryRouter>)
        await waitFor(() => screen.getByRole('button', { name: /save/i }))
        fireEvent.change(screen.getByRole('combobox'), { target: { value: 'ru' } })
        fireEvent.click(screen.getByRole('button', { name: /save/i }))
        await waitFor(() => expect(i18n.language).toBe('ru'))
    })

    it('does not re-load settings from DB when i18n language changes externally', async () => {
        let getSettingsCalls = 0
        server.use(
            http.get('http://localhost:8000/api/settings/', () => {
                getSettingsCalls++
                return HttpResponse.json({ default_language: 'en', default_folder: '' })
            })
        )
        render(<MemoryRouter><SettingsPage /></MemoryRouter>)
        await waitFor(() => expect(getSettingsCalls).toBe(1))
        // Simulate external language change (e.g. from another component)
        await i18n.changeLanguage('ru')
        // Give React time to process any potential effect re-runs
        await new Promise(r => setTimeout(r, 150))
        expect(getSettingsCalls).toBe(1)  // must NOT have re-fetched
    })
})
