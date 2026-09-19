import { describe, it, expect, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { server } from '@/test/server'
import { http, HttpResponse } from 'msw'
import { MemoryRouter } from 'react-router-dom'
import i18n from '@/i18n'
import { ModelsPage } from '../ModelsPage'

vi.mock('@/api/base', () => ({ getBaseUrl: async () => 'http://localhost:8000' }))

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
})
