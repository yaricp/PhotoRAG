import { act, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/server'
import i18n from '@/i18n'
import { PipelineWarningBanner } from '../PipelineWarningBanner'

const base = 'http://localhost:8000'

afterEach(() => { i18n.changeLanguage('en') })

describe('PipelineWarningBanner', () => {
    it('reports missing pipeline configurations in the selected language', async () => {
        i18n.changeLanguage('es')
        server.use(
            http.get(`${base}/api/models/`, () => HttpResponse.json([])),
            http.get(`${base}/api/system/status/`, () => HttpResponse.json({ ready: true, chat_ready: true, models: [] })),
        )

        render(<PipelineWarningBanner />)

        expect(await screen.findByText('Faltan configuraciones para algunos pasos del flujo:')).toBeInTheDocument()
        expect(screen.getByText(/Visión/)).toBeInTheDocument()
        expect(screen.getByText(/Configúralas en Configuración → Modelos\./)).toBeInTheDocument()
    })

    it('distinguishes configured but temporarily unavailable models from missing configuration', async () => {
        i18n.changeLanguage('ru')
        server.use(
            http.get(`${base}/api/models/`, () => HttpResponse.json(
                ['vision', 'clip', 'ocr', 'embedding', 'translator'].map((type, index) => ({
                    id: index + 1,
                    type,
                    mode: type === 'vision' ? 'local' : 'remote',
                    model_name: type === 'vision' ? 'qwen3-vl:2b-instruct' : `${type}-model`,
                    model_provider: 'openai',
                    api_key: 'test-key',
                })),
            )),
            http.get(`${base}/api/system/status/`, () => HttpResponse.json({
                ready: false, chat_ready: true, models: [{ name: 'vision', status: 'error', message: 'runner failed' }],
            })),
        )

        render(<PipelineWarningBanner />)

        expect(await screen.findByText('Настроенные модели временно недоступны:')).toBeInTheDocument()
        expect(screen.getByText(/Зрение \(описание фото\)/)).toBeInTheDocument()
        expect(screen.queryByText('Некоторые этапы конвейера не настроены:')).not.toBeInTheDocument()
    })

    it('accepts a configured Ollama role without an API key', async () => {
        const configs = ['vision', 'clip', 'ocr', 'embedding', 'translator'].map((type, index) => ({
            id: index + 1,
            type,
            mode: 'remote',
            model_name: `${type}-model`,
            model_provider: type === 'vision' ? 'ollama' : 'openai',
            api_key: type === 'vision' ? '' : 'test-key',
        }))
        server.use(
            http.get(`${base}/api/models/`, () => HttpResponse.json(configs)),
            http.get(`${base}/api/system/status/`, () => HttpResponse.json({ ready: true, chat_ready: true, models: [] })),
        )

        render(<PipelineWarningBanner />)

        await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument())
    })

    it('refreshes its warning after a model configuration is saved', async () => {
        let saved = false
        const configured = ['vision', 'clip', 'ocr', 'embedding', 'translator'].map((type, index) => ({
            id: index + 1,
            type,
            mode: 'remote',
            model_name: `${type}-model`,
            model_provider: 'openai',
            api_key: 'test-key',
        }))
        server.use(
            http.get(`${base}/api/models/`, () => HttpResponse.json(saved ? configured : [])),
            http.get(`${base}/api/system/status/`, () => HttpResponse.json({ ready: true, chat_ready: true, models: [] })),
        )

        render(<PipelineWarningBanner />)
        expect(await screen.findByText('Some pipeline steps are not configured:')).toBeInTheDocument()

        saved = true
        await act(async () => {
            window.dispatchEvent(new Event('photorag:model-configs-changed'))
        })
        await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument())
    })

    it('refreshes local availability when the worker status changes', async () => {
        let visionStatus = 'error'
        const configs = ['vision', 'clip', 'ocr', 'embedding', 'translator'].map((type, index) => ({
            id: index + 1,
            type,
            mode: type === 'vision' ? 'local' : 'remote',
            model_name: `${type}-model`,
            model_provider: 'openai',
            api_key: 'test-key',
        }))
        server.use(
            http.get(`${base}/api/models/`, () => HttpResponse.json(configs)),
            http.get(`${base}/api/system/status/`, () => HttpResponse.json({
                ready: visionStatus === 'ready',
                chat_ready: true,
                models: [{ name: 'vision', status: visionStatus, message: null }],
            })),
        )

        render(<PipelineWarningBanner />)
        expect(await screen.findByText('Configured models are temporarily unavailable:')).toBeInTheDocument()

        visionStatus = 'ready'
        await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument(), { timeout: 7000, interval: 100 })
    }, 8000)
})
