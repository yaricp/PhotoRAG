import { render, screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { ModelsPage } from '@/pages/ModelsPage'
import { server } from '@/test/server'
import { getModelSuggestions } from '@/utils/modelProviderOptions'

vi.mock('@/api/base', () => ({ getBaseUrl: async () => 'http://localhost:8000' }))

const unsupportedChatProviders = [
    /Google Vertex AI/i,
    /Groq/i,
    /Mistral AI/i,
    /Together AI/i,
    /Cohere/i,
]

describe('packaged provider options', () => {
    it('hides cloud chat providers that are not packaged-supported', async () => {
        server.use(
            http.get('http://localhost:8000/api/models/', () =>
                HttpResponse.json([
                    { id: 1, type: 'chat', mode: 'remote', model_name: 'gpt-4o-mini', model_provider: 'openai' },
                ])
            )
        )

        render(<MemoryRouter><ModelsPage /></MemoryRouter>)

        await screen.findByText('Chat (AI agent)')
        const providerSelect = screen.getAllByRole('combobox')[1]
        expect(within(providerSelect).getByRole('option', { name: 'OpenAI' })).toBeInTheDocument()
        expect(within(providerSelect).getByRole('option', { name: /Anthropic/i })).toBeInTheDocument()
        expect(within(providerSelect).getByRole('option', { name: /Google Gemini/i })).toBeInTheDocument()
        expect(within(providerSelect).getByRole('option', { name: /Local via Ollama/i })).toBeInTheDocument()

        unsupportedChatProviders.forEach(name => {
            expect(within(providerSelect).queryByRole('option', { name })).not.toBeInTheDocument()
        })
    })

    it('does not offer Anthropic for embeddings because Anthropic has no embeddings API', async () => {
        server.use(
            http.get('http://localhost:8000/api/models/', () =>
                HttpResponse.json([
                    { id: 1, type: 'embedding', mode: 'remote', model_name: 'text-embedding-3-small', model_provider: 'openai' },
                ])
            )
        )

        render(<MemoryRouter><ModelsPage /></MemoryRouter>)

        await screen.findByText('Embedding (semantic search)')
        const providerSelect = screen.getAllByRole('combobox')[1]
        expect(within(providerSelect).getByRole('option', { name: 'OpenAI' })).toBeInTheDocument()
        expect(within(providerSelect).getByRole('option', { name: /Google Gemini/i })).toBeInTheDocument()
        expect(within(providerSelect).getByRole('option', { name: /Local via Ollama/i })).toBeInTheDocument()
        expect(within(providerSelect).queryByRole('option', { name: /Anthropic/i })).not.toBeInTheDocument()
    })

    it('suggests Ollama embedding models for semantic search', () => {
        expect(getModelSuggestions('ollama', 'embedding')).toEqual([
            'nomic-embed-text',
            'mxbai-embed-large',
        ])
    })
})
