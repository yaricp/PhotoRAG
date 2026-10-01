import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { MemoryRouter } from 'react-router-dom'
import i18n from '@/i18n'
import { server } from '@/test/server'
import { makePipelineTask } from '@/test/factories'
import type { PipelineRun } from '@/types/api'
import { JobProcessingPage } from '../JobProcessingPage'

vi.mock('@/api/base', () => ({ getBaseUrl: async () => 'http://localhost:8000' }))

afterEach(() => { i18n.changeLanguage('en') })

const renderPage = () => render(<MemoryRouter><JobProcessingPage /></MemoryRouter>)

function makeProcessingRun(runId: number, photoId: number, taskId: number, error: string): PipelineRun {
    return {
        run_id: runId,
        photo_id: photoId,
        source: 'manual',
        status: 'completed-with-errors',
        summary: error,
        created_at: '2026-01-01T00:00:00Z',
        started_at: '2026-01-01T00:00:01Z',
        finished_at: '2026-01-01T00:00:02Z',
        queue_position: null,
        wait_seconds: 2,
        photo: {
            id: photoId,
            file_path: `/photos/${photoId}.jpg`,
            description: null,
            translated_description: null,
            ocr_text: null,
            tags: [],
            categories: [],
        },
        tasks: [{
            ...makePipelineTask({ id: taskId, photo_id: photoId, status: 'failed', error }),
            run_id: runId,
            attempt: 1,
            skip_reason: null,
            required: true,
        }],
    }
}

describe('JobProcessingPage', () => {
    it('renders Russian processing UI', async () => {
        i18n.changeLanguage('ru')
        renderPage()
        expect(await screen.findByText('Нет активной обработки')).toBeInTheDocument()
    })

    it('shows a queued photo position and elapsed wait', async () => {
        const queued = makeProcessingRun(58, 13, 59, 'queued')
        queued.status = 'queued'
        queued.tasks = []
        queued.queue_position = 3
        queued.wait_seconds = 130
        server.use(
            http.get('http://localhost:8000/api/pipeline/runs', () =>
                HttpResponse.json({ items: [queued], total: 1, page: 1, size: 20, pages: 1 })
            )
        )

        renderPage()

        expect(await screen.findByText('Queue position: 3 · Waiting 2m 10s')).toBeInTheDocument()
    })

    it('shows paginated completed runs with saved photo outputs and task errors', async () => {
        const requestedPages: string[] = []
        server.use(
            http.get('http://localhost:8000/api/pipeline/runs', ({ request }) => {
                const url = new URL(request.url)
                const bucket = url.searchParams.get('bucket')
                const page = url.searchParams.get('page') ?? '1'
                if (bucket === 'active') {
                    return HttpResponse.json({ items: [], total: 0, page: 1, size: 20, pages: 1 })
                }
                requestedPages.push(page)
                const firstRun = {
                    run_id: 90,
                    photo_id: 7,
                    source: 'watcher',
                    status: 'completed-with-errors',
                    summary: 'vision_task: runner stopped',
                    created_at: '2026-01-02T00:00:00Z',
                    started_at: '2026-01-02T00:00:01Z',
                    finished_at: '2026-01-02T00:00:02Z',
                    queue_position: null,
                    wait_seconds: 2,
                    photo: {
                        id: 7,
                        file_path: '/photos/7.jpg',
                        description: 'Sunset over the lake',
                        translated_description: 'Закат над озером',
                        ocr_text: null,
                        tags: ['sunset'],
                        categories: ['landscape'],
                    },
                    tasks: [{
                        id: 111,
                        run_id: 90,
                        photo_id: 7,
                        attempt: 2,
                        phase: 'phase_1',
                        task_name: 'vision_task',
                        status: 'failed',
                        error: 'runner stopped',
                        skip_reason: null,
                        required: true,
                        started_at: '2026-01-02T00:00:01Z',
                        finished_at: '2026-01-02T00:00:02Z',
                        created_at: '2026-01-02T00:00:01Z',
                    }],
                }
                return HttpResponse.json({
                    items: [page === '1' ? firstRun : { ...firstRun, run_id: 89, photo_id: 6, photo: { ...firstRun.photo, id: 6, description: 'A forest path' } }],
                    total: 2,
                    page: Number(page),
                    size: 1,
                    pages: 2,
                })
            })
        )

        renderPage()
        fireEvent.click(await screen.findByRole('tab', { name: 'Completed' }))

        expect(await screen.findByText('Sunset over the lake')).toBeInTheDocument()
        expect(screen.getByText('Закат над озером')).toBeInTheDocument()
        expect(screen.getByText('sunset')).toBeInTheDocument()
        expect(screen.getByText('runner stopped')).toBeInTheDocument()
        fireEvent.click(screen.getByRole('button', { name: 'Next' }))
        expect(await screen.findByText('A forest path')).toBeInTheDocument()
        expect(requestedPages).toContain('2')
    })

    it('retries a failed pipeline task', async () => {
        let retryTaskId: string | undefined
        server.use(
            http.get('http://localhost:8000/api/pipeline/runs', ({ request }) => {
                const bucket = new URL(request.url).searchParams.get('bucket')
                return HttpResponse.json({
                    items: bucket === 'active' ? [] : [makeProcessingRun(42, 7, 42, 'rate limit')],
                    total: bucket === 'active' ? 0 : 1,
                    page: 1,
                    size: 20,
                    pages: 1,
                })
            }),
            http.post('http://localhost:8000/api/pipeline/tasks/:taskId/retry', ({ params }) => {
                retryTaskId = String(params.taskId)
                return HttpResponse.json({ status: 'queued', task_id: 42, photo_id: 7, task_name: 'auto_tag_clip_task' })
            })
        )

        renderPage()
        fireEvent.click(await screen.findByRole('tab', { name: 'Completed' }))
        fireEvent.click(await screen.findByRole('button', { name: 'Retry' }))

        await waitFor(() => expect(retryTaskId).toBe('42'))
    })

    it('resumes only the selected interrupted run', async () => {
        let resumedRunId: string | undefined
        const interrupted = makeProcessingRun(55, 12, 56, 'backend stopped')
        interrupted.status = 'interrupted'
        server.use(
            http.get('http://localhost:8000/api/pipeline/runs', ({ request }) => {
                const bucket = new URL(request.url).searchParams.get('bucket')
                return HttpResponse.json({
                    items: bucket === 'active' ? [] : [interrupted],
                    total: bucket === 'active' ? 0 : 1,
                    page: 1,
                    size: 20,
                    pages: 1,
                })
            }),
            http.post('http://localhost:8000/api/pipeline/runs/:runId/resume', ({ params }) => {
                resumedRunId = String(params.runId)
                return HttpResponse.json({ status: 'queued', run_id: 57, resumed_from_run_id: 55 })
            })
        )

        renderPage()
        fireEvent.click(await screen.findByRole('tab', { name: 'Completed' }))
        fireEvent.click(await screen.findByRole('button', { name: 'Resume this run' }))

        await waitFor(() => expect(resumedRunId).toBe('55'))
    })

    it('confirms and reruns the full pipeline for a failed photo', async () => {
        let rerunPhotoId: string | undefined
        server.use(
            http.get('http://localhost:8000/api/pipeline/runs', ({ request }) => {
                const bucket = new URL(request.url).searchParams.get('bucket')
                return HttpResponse.json({
                    items: bucket === 'active' ? [] : [makeProcessingRun(43, 8, 43, 'model error')],
                    total: bucket === 'active' ? 0 : 1,
                    page: 1,
                    size: 20,
                    pages: 1,
                })
            }),
            http.post('http://localhost:8000/api/photos/:photoId/run-pipeline', ({ params }) => {
                rerunPhotoId = String(params.photoId)
                return HttpResponse.json({ status: 'queued', photo_id: Number(params.photoId) })
            })
        )

        renderPage()
        fireEvent.click(await screen.findByRole('tab', { name: 'Completed' }))
        fireEvent.click(await screen.findByRole('button', { name: 'Run pipeline again' }))
        fireEvent.click(await screen.findByRole('button', { name: 'Run again' }))

        await waitFor(() => expect(rerunPhotoId).toBe('8'))
    })
})
