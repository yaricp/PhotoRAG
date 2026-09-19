import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { MemoryRouter } from 'react-router-dom'
import i18n from '@/i18n'
import { server } from '@/test/server'
import { makePipelineTask } from '@/test/factories'
import { JobProcessingPage } from '../JobProcessingPage'

vi.mock('@/api/base', () => ({ getBaseUrl: async () => 'http://localhost:8000' }))

afterEach(() => { i18n.changeLanguage('en') })

const renderPage = () => render(<MemoryRouter><JobProcessingPage /></MemoryRouter>)

describe('JobProcessingPage', () => {
    it('renders Russian processing UI', async () => {
        i18n.changeLanguage('ru')
        renderPage()
        expect(await screen.findByText('Нет активной обработки')).toBeInTheDocument()
    })

    it('retries a failed pipeline task', async () => {
        let retryTaskId: string | undefined
        server.use(
            http.get('http://localhost:8000/api/pipeline/active', () => HttpResponse.json([])),
            http.get('http://localhost:8000/api/pipeline/recent', () =>
                HttpResponse.json([
                    makePipelineTask({
                        id: 42,
                        photo_id: 7,
                        status: 'failed',
                        error: 'rate limit',
                    }),
                ])
            ),
            http.post('http://localhost:8000/api/pipeline/tasks/:taskId/retry', ({ params }) => {
                retryTaskId = String(params.taskId)
                return HttpResponse.json({ status: 'queued', task_id: 42, photo_id: 7, task_name: 'auto_tag_clip_task' })
            })
        )

        renderPage()
        fireEvent.click(await screen.findByRole('button', { name: 'Retry' }))

        await waitFor(() => expect(retryTaskId).toBe('42'))
    })

    it('confirms and reruns the full pipeline for a failed photo', async () => {
        let rerunPhotoId: string | undefined
        server.use(
            http.get('http://localhost:8000/api/pipeline/active', () => HttpResponse.json([])),
            http.get('http://localhost:8000/api/pipeline/recent', () =>
                HttpResponse.json([
                    makePipelineTask({
                        id: 43,
                        photo_id: 8,
                        status: 'failed',
                        error: 'model error',
                    }),
                ])
            ),
            http.post('http://localhost:8000/api/photos/:photoId/run-pipeline', ({ params }) => {
                rerunPhotoId = String(params.photoId)
                return HttpResponse.json({ status: 'queued', photo_id: Number(params.photoId) })
            })
        )

        renderPage()
        fireEvent.click(await screen.findByRole('button', { name: 'Run pipeline again' }))
        fireEvent.click(await screen.findByRole('button', { name: 'Run again' }))

        await waitFor(() => expect(rerunPhotoId).toBe('8'))
    })
})
