import { describe, it, expect, afterEach, beforeEach } from 'vitest'
import { render, screen, within } from '@testing-library/react'
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
    it('shows the compact Ollama model for OCR and chat on Windows', async () => {
        Object.defineProperty(window, 'electronAPI', {
            value: { platform: 'win32' },
            writable: true,
            configurable: true,
        })
        server.use(
            http.get('http://localhost:8000/api/models/', () =>
                HttpResponse.json([
                    { id: 1, type: 'ocr', mode: 'remote', model_name: 'qwen3-vl:2b-instruct', model_provider: 'ollama' },
                    { id: 2, type: 'chat', mode: 'remote', model_name: 'qwen3-vl:2b-instruct', model_provider: 'ollama' },
                ])
            )
        )

        render(<MemoryRouter><ModelsPage /></MemoryRouter>)
        const ocrCard = (await screen.findByText('OCR (text extraction)')).closest('.model-card') as HTMLElement
        const chatCard = screen.getByText('Chat (AI agent)').closest('.model-card') as HTMLElement
        const ocrSuggestion = within(ocrCard).getByRole('button', { name: 'qwen3-vl:2b-instruct' })
        expect(ocrSuggestion).toBeInTheDocument()
        expect(within(chatCard).getByRole('button', { name: 'qwen3-vl:2b-instruct' })).toBeInTheDocument()
        const ocrProvider = within(ocrCard).getAllByRole('combobox')[1]
        expect(ocrProvider.compareDocumentPosition(ocrSuggestion) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    })

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
        expect(await screen.findByText(/Выберите модель для каждой функции/)).toBeInTheDocument()
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

        expect(await screen.findByText(/Built-in local models are not available in this Windows build/i)).toBeInTheDocument()
        expect(screen.queryByRole('option', { name: /^Local \(GPU \/ CPU\)$/i })).not.toBeInTheDocument()
        expect(screen.getAllByDisplayValue('gpt-4o-mini').length).toBeGreaterThanOrEqual(1)
        expect(screen.getByDisplayValue('text-embedding-3-small')).toBeInTheDocument()
    })
})
