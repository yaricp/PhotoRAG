import { describe, it, expect, afterEach, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { server } from '@/test/server'
import { http, HttpResponse } from 'msw'
import { MemoryRouter } from 'react-router-dom'
import i18n from '@/i18n'
import { ModelsPage } from '../ModelsPage'

vi.mock('@/api/base', () => ({ getBaseUrl: async () => 'http://localhost:8000' }))

beforeEach(() => {
    Object.defineProperty(window, 'electronAPI', {
        value: { platform: 'darwin' },
        writable: true,
        configurable: true,
    })
})

afterEach(() => { i18n.changeLanguage('en') })

describe('ModelsPage i18n', () => {
    it('renders clearer Russian model labels', async () => {
        i18n.changeLanguage('ru')
        server.use(
            http.get('http://localhost:8000/api/models/', () =>
                HttpResponse.json([
                    { id: 1, type: 'vision', mode: 'remote', model_name: 'gpt-4o-mini' },
                    { id: 2, type: 'clip', mode: 'remote', model_name: 'gpt-4o-mini' },
                    { id: 3, type: 'embedding', mode: 'remote', model_name: 'text-embedding-3-small' },
                ])
            )
        )
        render(<MemoryRouter><ModelsPage /></MemoryRouter>)
        expect(await screen.findByText('Зрение (описание фото)')).toBeInTheDocument()
        expect(await screen.findByText('CLIP (теги и категории)')).toBeInTheDocument()
        expect(await screen.findByText('Эмбеддинг (семантический поиск)')).toBeInTheDocument()
    })

    it('renders Russian models description', async () => {
        i18n.changeLanguage('ru')
        render(<MemoryRouter><ModelsPage /></MemoryRouter>)
        expect(await screen.findByText(/Настройте модели/)).toBeInTheDocument()
    })


    it('hides local model mode and shows a Windows notice on Windows', async () => {
        Object.defineProperty(window, 'electronAPI', {
            value: { platform: 'win32' },
            writable: true,
            configurable: true,
        })
        server.use(
            http.get('http://localhost:8000/api/models/', () =>
                HttpResponse.json([
                    { id: 1, type: 'vision', mode: 'local', model_name: 'Qwen/Qwen2-VL-2B-Instruct' },
                    { id: 2, type: 'embedding', mode: 'local', model_name: 'nomic-ai/nomic-embed-text-v1.5' },
                ])
            )
        )

        render(<MemoryRouter><ModelsPage /></MemoryRouter>)

        expect(await screen.findByText(/Local models are temporarily unavailable on Windows/i)).toBeInTheDocument()
        expect(screen.queryByRole('option', { name: /Local/i })).not.toBeInTheDocument()
        expect(screen.getAllByDisplayValue('gpt-4o-mini').length).toBeGreaterThanOrEqual(1)
        expect(screen.getByDisplayValue('text-embedding-3-small')).toBeInTheDocument()
    })
})
