import { describe, it, expect, afterEach, vi } from 'vitest'
import { act, render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { MemoryRouter } from 'react-router-dom'
import i18n from '@/i18n'
import { server } from '@/test/server'
import { makePipelineTask } from '@/test/factories'
import type { PipelineRun, PipelineRunTask } from '@/types/api'
import { JobProcessingPage } from '../JobProcessingPage'

vi.mock('@/api/base', () => ({ getBaseUrl: async () => 'http://localhost:8000' }))

afterEach(() => { i18n.changeLanguage('en') })

const renderPage = () => render(<MemoryRouter><JobProcessingPage /></MemoryRouter>)

function makeProcessingRun(runId: number, photoId: number, taskId: number, error: string): PipelineRun {
    const task: PipelineRunTask = {
        ...makePipelineTask({ id: taskId, photo_id: photoId, status: 'failed', error }),
        run_id: runId,
        attempt: 1,
        skip_reason: null,
        required: true,
    }
    return {
        run_id: runId,
        photo_id: photoId,
        attempt_count: 1,
        attempts: [{
            run_id: runId,
            source: 'manual',
            status: 'completed-with-errors',
            summary: error,
            created_at: '2026-01-01T00:00:00Z',
            started_at: '2026-01-01T00:00:01Z',
            finished_at: '2026-01-01T00:00:02Z',
            tasks: [task],
        }],
        is_task_retry: false,
        retry_tasks: [],
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
        tasks: [task],
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

    it('keeps both distinct-photo counts visible and collapses completed outputs by default', async () => {
        const active = makeProcessingRun(71, 21, 81, 'running')
        active.status = 'running'
        active.tasks[0].status = 'running'
        active.photo.description = 'A previous description that must stay hidden'
        const completed = makeProcessingRun(72, 22, 82, 'tag retry failed')
        completed.photo.description = 'A completed description'
        completed.attempt_count = 3
        completed.attempts = Array.from({ length: 3 }, (_, index) => ({
            ...completed.attempts[0],
            run_id: 72 - 2 + index,
            status: index === 2 ? 'completed-with-errors' : 'completed',
        }))
        server.use(
            http.get('http://localhost:8000/api/pipeline/runs', ({ request }) => {
                const bucket = new URL(request.url).searchParams.get('bucket')
                return HttpResponse.json({
                    items: bucket === 'active' ? [active] : [completed],
                    total: bucket === 'active' ? 2 : 3,
                    active_total: 2,
                    completed_total: 3,
                    page: 1,
                    size: 20,
                    pages: 1,
                })
            })
        )

        renderPage()
        const activeTab = await screen.findByRole('tab', { name: /In progress/ })
        const completedTab = screen.getByRole('tab', { name: /Completed/ })
        await waitFor(() => {
            expect(activeTab).toHaveTextContent('2')
            expect(completedTab).toHaveTextContent('3')
        })
        fireEvent.click(completedTab)
        expect(await screen.findByText('Photo #22')).toBeInTheDocument()
        expect(screen.getByText('A completed description')).not.toBeVisible()
        expect(screen.getByText('Attempts: 3')).toBeInTheDocument()
        fireEvent.click(screen.getByText('Show results'))
        expect(await screen.findByText('A completed description')).toBeInTheDocument()
    })

    it('hides saved outputs while a task retry is queued or running', async () => {
        const retry = makeProcessingRun(80, 23, 90, 'previous attempt failed')
        retry.status = 'queued'
        retry.is_task_retry = true
        retry.photo.description = 'Description from an earlier attempt'
        server.use(
            http.get('http://localhost:8000/api/pipeline/runs', () =>
                HttpResponse.json({ items: [retry], total: 1, page: 1, size: 20, pages: 1 })
            )
        )

        renderPage()
        expect(await screen.findByText('Photo #23')).toBeInTheDocument()
        expect(screen.queryByText('Description from an earlier attempt')).not.toBeInTheDocument()
    })

    it('shows the planned task names by phase while a retry is still queued', async () => {
        const retry = makeProcessingRun(81, 24, 91, 'previous attempt failed')
        retry.status = 'queued'
        retry.is_task_retry = true
        retry.photo.description = 'Description from an earlier attempt'
        retry.tasks = []
        retry.attempts[0].tasks = []
        Object.assign(retry, { retry_tasks: [
            { task_name: 'vision_task', phase: 'phase_1' },
            { task_name: 'translate_description_task', phase: 'phase_2' },
        ] })
        server.use(
            http.get('http://localhost:8000/api/pipeline/runs', () =>
                HttpResponse.json({ items: [retry], total: 1, page: 1, size: 20, pages: 1 })
            )
        )

        renderPage()
        expect(await screen.findByText('vision')).toBeInTheDocument()
        expect(screen.getByText('translate description')).toBeInTheDocument()
        expect(screen.getByText('phase 1')).toBeInTheDocument()
        expect(screen.getByText('phase 2')).toBeInTheDocument()
        expect(screen.queryByText('Description from an earlier attempt')).not.toBeInTheDocument()
    })

    it('loads the startup retry preference as off by default and persists the toggle', async () => {
        const savedSettings: Array<{ key: string; value: string }> = []
        server.use(
            http.get('http://localhost:8000/api/settings/', () => HttpResponse.json({})),
            http.put('http://localhost:8000/api/settings/:key', async ({ params, request }) => {
                const body = await request.json() as { value: string }
                savedSettings.push({ key: String(params.key), value: body.value })
                return HttpResponse.json({ key: params.key, value: body.value })
            }),
            http.get('http://localhost:8000/api/pipeline/retry-eligible/count', () =>
                HttpResponse.json({ eligible_photos: 0, eligible_tasks: 0 })
            )
        )

        renderPage()
        const toggle = await screen.findByRole('checkbox', { name: /Retry unfinished tasks at startup/ })
        expect(toggle).not.toBeChecked()
        fireEvent.click(toggle)

        await waitFor(() => expect(savedSettings).toEqual([
            { key: 'retry_unfinished_at_startup', value: 'true' },
        ]))
        expect(toggle).toBeChecked()
    })

    it('restarts all eligible tasks with one action and reports queued progress', async () => {
        let bulkRetryCalls = 0
        const queued = makeProcessingRun(101, 33, 102, 'queued')
        queued.status = 'queued'
        queued.tasks = []
        queued.attempts[0].tasks = []
        queued.queue_position = 2
        server.use(
            http.get('http://localhost:8000/api/settings/', () => HttpResponse.json({ retry_unfinished_at_startup: 'false' })),
            http.get('http://localhost:8000/api/pipeline/runs', ({ request }) => {
                const bucket = new URL(request.url).searchParams.get('bucket')
                const items = bucket === 'active' && bulkRetryCalls ? [queued] : []
                return HttpResponse.json({
                    items,
                    total: items.length,
                    active_total: items.length,
                    completed_total: 0,
                    page: 1,
                    size: 20,
                    pages: 1,
                })
            }),
            http.get('http://localhost:8000/api/pipeline/retry-eligible/count', () =>
                HttpResponse.json({ eligible_photos: bulkRetryCalls ? 0 : 2, eligible_tasks: bulkRetryCalls ? 0 : 5 })
            ),
            http.post('http://localhost:8000/api/pipeline/retry-eligible', () => {
                bulkRetryCalls += 1
                return HttpResponse.json({ status: 'queued', queued_photos: 2, queued_tasks: 5, run_ids: [101, 102] }, { status: 202 })
            })
        )

        renderPage()
        const button = await screen.findByRole('button', { name: 'Restart all failed and unfinished tasks' })
        expect(button).toHaveClass('jobs-page__bulk-retry-btn')
        expect(button).toBeEnabled()
        fireEvent.click(button)

        await waitFor(() => expect(bulkRetryCalls).toBe(1))
        expect(await screen.findByText('Queued retries for 2 photos (5 tasks).')).toBeInTheDocument()
        expect(await screen.findByText('Photo #33')).toBeInTheDocument()
        expect(screen.getByText('Queue position: 2 · Waiting 2s')).toBeInTheDocument()
        expect(button).toBeDisabled()
    })

    it('does not let an older empty active-list response erase bulk retry cards', async () => {
        let releaseStaleResponse: () => void = () => {}
        let staleResponseStarted: () => void = () => {}
        let staleResponseFinished = false
        let bulkRetryCalls = 0
        let activeRequests = 0
        const staleRequestStarted = new Promise<void>(resolve => { staleResponseStarted = resolve })
        const queued = makeProcessingRun(101, 33, 102, 'queued')
        queued.status = 'queued'
        queued.tasks = []
        queued.attempts[0].tasks = []
        queued.queue_position = 1
        server.use(
            http.get('http://localhost:8000/api/settings/', () => HttpResponse.json({ retry_unfinished_at_startup: 'false' })),
            http.get('http://localhost:8000/api/pipeline/runs', async ({ request }) => {
                const bucket = new URL(request.url).searchParams.get('bucket')
                if (bucket !== 'active') {
                    return HttpResponse.json({ items: [], total: 0, page: 1, size: 20, pages: 1 })
                }
                activeRequests += 1
                if (activeRequests === 1) {
                    staleResponseStarted()
                    await new Promise<void>(resolve => { releaseStaleResponse = resolve })
                    staleResponseFinished = true
                    return HttpResponse.json({ items: [], total: 0, page: 1, size: 20, pages: 1 })
                }
                const items = bulkRetryCalls ? [queued] : []
                return HttpResponse.json({ items, total: items.length, active_total: items.length, completed_total: 0, page: 1, size: 20, pages: 1 })
            }),
            http.get('http://localhost:8000/api/pipeline/retry-eligible/count', () =>
                HttpResponse.json({ eligible_photos: bulkRetryCalls ? 0 : 1, eligible_tasks: bulkRetryCalls ? 0 : 1 })
            ),
            http.post('http://localhost:8000/api/pipeline/retry-eligible', () => {
                bulkRetryCalls += 1
                return HttpResponse.json({ status: 'queued', queued_photos: 1, queued_tasks: 1, run_ids: [101] }, { status: 202 })
            })
        )

        renderPage()
        await staleRequestStarted
        fireEvent.click(await screen.findByRole('button', { name: 'Restart all failed and unfinished tasks' }))
        expect(await screen.findByText('Photo #33')).toBeInTheDocument()

        await act(async () => {
            releaseStaleResponse()
            await waitFor(() => expect(staleResponseFinished).toBe(true))
            await new Promise(resolve => setTimeout(resolve, 0))
        })

        expect(screen.getByText('Photo #33')).toBeInTheDocument()
        expect(screen.getByText('Queue position: 1 · Waiting 2s')).toBeInTheDocument()
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
        fireEvent.click(await screen.findByRole('tab', { name: /Completed/ }))

        expect(screen.queryByText('Sunset over the lake')).not.toBeInTheDocument()
        fireEvent.click(await screen.findByText('Show results'))
        expect(await screen.findByText('Sunset over the lake')).toBeInTheDocument()
        expect(screen.getByText('Закат над озером')).toBeInTheDocument()
        expect(screen.getByText('sunset')).toBeInTheDocument()
        expect(screen.getByText('runner stopped')).toBeInTheDocument()
        fireEvent.click(screen.getByRole('button', { name: 'Next' }))
        fireEvent.click(await screen.findByText('Show results'))
        expect(await screen.findByText('A forest path')).toBeInTheDocument()
        expect(requestedPages).toContain('2')
    })

    it('keeps an old failed attempt visible when a photo has more than 50 tasks and is rerun', async () => {
        let rerunPhotoId: string | undefined
        const history = makeProcessingRun(70, 14, 100, 'original task failure')
        history.summary = 'task 0: original task failure'
        history.tasks = Array.from({ length: 55 }, (_, index) => ({
            ...makePipelineTask({
                id: 100 + index,
                photo_id: 14,
                phase: `phase_${Math.floor(index / 10)}`,
                task_name: `task_${index}_task`,
                status: index === 0 ? 'failed' : 'done',
                error: index === 0 ? 'original task failure' : null,
            }),
            run_id: 70,
            attempt: 1,
            skip_reason: null,
            required: true,
        }))
        history.attempts[0].tasks = history.tasks
        server.use(
            http.get('http://localhost:8000/api/pipeline/runs', ({ request }) => {
                const bucket = new URL(request.url).searchParams.get('bucket')
                return HttpResponse.json({
                    items: bucket === 'active' ? [] : [history],
                    total: bucket === 'active' ? 0 : 1,
                    page: 1,
                    size: 20,
                    pages: 1,
                })
            }),
            http.post('http://localhost:8000/api/photos/:photoId/run-pipeline', ({ params }) => {
                rerunPhotoId = String(params.photoId)
                return HttpResponse.json({ status: 'queued', photo_id: 14, run_id: 71 })
            })
        )

        renderPage()
        fireEvent.click(await screen.findByRole('tab', { name: /Completed/ }))
        expect(await screen.findByText('task 54')).toBeInTheDocument()
        expect(screen.getByText('Run #70')).toBeInTheDocument()
        fireEvent.click(screen.getByRole('button', { name: 'Run pipeline again' }))
        fireEvent.click(await screen.findByRole('button', { name: 'Run again' }))

        await waitFor(() => expect(rerunPhotoId).toBe('14'))
        expect(screen.getByText('Run #70')).toBeInTheDocument()
        expect(screen.getByText(/task 0: original task failure/)).toBeInTheDocument()
        expect(screen.getByText('original task failure')).toBeInTheDocument()
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
        fireEvent.click(await screen.findByRole('tab', { name: /Completed/ }))
        fireEvent.click(await screen.findByRole('button', { name: 'Retry' }))

        await waitFor(() => expect(retryTaskId).toBe('42'))
    })

    it('keeps failed-task retry available on an older failed attempt', async () => {
        let retryTaskId: string | undefined
        const history = makeProcessingRun(92, 7, 93, 'tag persistence failed')
        const oldAttempt = { ...history.attempts[0], run_id: 91, status: 'completed-with-errors' as const }
        oldAttempt.tasks[0].run_id = 91
        oldAttempt.tasks[0].id = 91
        const succeeded = { ...history.tasks[0], id: 94, run_id: 92, status: 'done' as const, error: null }
        const currentAttempt = {
            ...history.attempts[0],
            run_id: 92,
            status: 'completed' as const,
            summary: '',
            tasks: [succeeded],
        }
        history.run_id = 92
        history.status = 'completed'
        history.summary = ''
        history.attempt_count = 2
        history.attempts = [oldAttempt, currentAttempt]
        history.tasks = [succeeded]
        server.use(
            http.get('http://localhost:8000/api/pipeline/runs', ({ request }) => {
                const bucket = new URL(request.url).searchParams.get('bucket')
                return HttpResponse.json({
                    items: bucket === 'active' ? [] : [history],
                    total: bucket === 'active' ? 0 : 1,
                    page: 1,
                    size: 20,
                    pages: 1,
                })
            }),
            http.post('http://localhost:8000/api/pipeline/tasks/:taskId/retry', ({ params }) => {
                retryTaskId = String(params.taskId)
                return HttpResponse.json({ status: 'queued', task_id: 91, photo_id: 7, task_name: 'auto_tag_clip_task' })
            })
        )

        renderPage()
        fireEvent.click(await screen.findByRole('tab', { name: /Completed/ }))
        expect(await screen.findByText('Photo #7')).toBeInTheDocument()
        fireEvent.click(screen.getByText('Previous attempts (1)'))
        fireEvent.click(await screen.findByRole('button', { name: 'Retry' }))

        await waitFor(() => expect(retryTaskId).toBe('91'))
    })

    it('shows the latest successful attempt and collapses older failed attempts', async () => {
        const history = makeProcessingRun(102, 30, 103, 'old tag attempt failed')
        const failedTask = { ...history.tasks[0], run_id: 101, id: 101, task_name: 'auto_tag_clip_task' }
        const oldAttempt = { ...history.attempts[0], run_id: 101, status: 'completed-with-errors' as const, tasks: [failedTask] }
        const succeededTask = { ...history.tasks[0], run_id: 102, id: 102, task_name: 'auto_tag_clip_task', status: 'done' as const, error: null }
        history.run_id = 102
        history.status = 'completed'
        history.summary = ''
        history.attempt_count = 2
        history.attempts = [oldAttempt, { ...history.attempts[0], run_id: 102, status: 'completed' as const, tasks: [succeededTask] }]
        history.tasks = [succeededTask]
        server.use(
            http.get('http://localhost:8000/api/pipeline/runs', ({ request }) => {
                const bucket = new URL(request.url).searchParams.get('bucket')
                return HttpResponse.json({ items: bucket === 'active' ? [] : [history], total: 1, page: 1, size: 20, pages: 1 })
            })
        )

        renderPage()
        fireEvent.click(await screen.findByRole('tab', { name: /Completed/ }))
        expect(await screen.findByText('Photo #30')).toBeInTheDocument()

        const latestTask = screen.getAllByText('auto tag clip')[0].closest('.task-chip')
        expect(latestTask).toHaveClass('task-chip--done')
        const previousSummary = screen.getByText('Previous attempts (1)')
        const oldHistory = previousSummary.closest('details') as HTMLElement
        expect(within(oldHistory).getByText('old tag attempt failed')).not.toBeVisible()
        fireEvent.click(previousSummary)
        expect(within(oldHistory).getByText('old tag attempt failed')).toBeVisible()
        expect(within(oldHistory).getByRole('button', { name: 'Retry' })).toBeVisible()
    })

    it('keeps the latest failed task and its retry visible while collapsing older failures', async () => {
        const history = makeProcessingRun(112, 31, 113, 'latest tag attempt failed')
        const oldTask = { ...history.tasks[0], run_id: 111, id: 111, task_name: 'auto_tag_clip_task', error: 'older tag attempt failed' }
        const oldAttempt = { ...history.attempts[0], run_id: 111, status: 'completed-with-errors' as const, tasks: [oldTask] }
        const latestTask = { ...history.tasks[0], run_id: 112, id: 112, task_name: 'auto_tag_clip_task', error: 'latest tag attempt failed' }
        const currentAttempt = {
            ...history.attempts[0],
            run_id: 112,
            status: 'completed-with-errors' as const,
            summary: 'latest tag attempt failed',
            tasks: [latestTask],
        }
        history.run_id = 112
        history.status = 'completed-with-errors'
        history.summary = 'latest tag attempt failed'
        history.attempt_count = 2
        history.attempts = [oldAttempt, currentAttempt]
        history.tasks = [latestTask]
        server.use(
            http.get('http://localhost:8000/api/pipeline/runs', ({ request }) => {
                const bucket = new URL(request.url).searchParams.get('bucket')
                return HttpResponse.json({ items: bucket === 'active' ? [] : [history], total: 1, page: 1, size: 20, pages: 1 })
            })
        )

        renderPage()
        fireEvent.click(await screen.findByRole('tab', { name: /Completed/ }))
        expect(await screen.findByText('Photo #31')).toBeInTheDocument()
        const latestFailure = screen.getAllByText('latest tag attempt failed').find(element =>
            element.classList.contains('task-chip__detail')
        )
        expect(latestFailure).toBeVisible()
        const latestTaskChip = latestFailure?.closest('.task-chip')
        expect(within(latestTaskChip as HTMLElement).getByRole('button', { name: 'Retry' })).toBeVisible()

        const previousSummary = screen.getByText('Previous attempts (1)')
        const oldHistory = previousSummary.closest('details') as HTMLElement
        expect(within(oldHistory).getByText('older tag attempt failed')).not.toBeVisible()
        fireEvent.click(previousSummary)
        expect(within(oldHistory).getByText('older tag attempt failed')).toBeVisible()
        expect(screen.getAllByRole('button', { name: 'Retry' })).toHaveLength(2)
    })

    it('does not show a full-pipeline rerun button on an active photo card', async () => {
        const active = makeProcessingRun(93, 8, 95, 'processing')
        active.status = 'running'
        active.attempts[0].status = 'running'
        active.tasks[0].status = 'running'
        active.attempts[0].tasks = active.tasks
        server.use(
            http.get('http://localhost:8000/api/pipeline/runs', ({ request }) => {
                const bucket = new URL(request.url).searchParams.get('bucket')
                return HttpResponse.json({
                    items: bucket === 'active' ? [active] : [],
                    total: bucket === 'active' ? 1 : 0,
                    active_total: bucket === 'active' ? 1 : 0,
                    completed_total: 0,
                    page: 1,
                    size: 20,
                    pages: 1,
                })
            })
        )

        renderPage()

        expect(await screen.findByText('Photo #8')).toBeInTheDocument()
        expect(screen.queryByRole('button', { name: 'Run pipeline again' })).not.toBeInTheDocument()
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
        fireEvent.click(await screen.findByRole('tab', { name: /Completed/ }))
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
        fireEvent.click(await screen.findByRole('tab', { name: /Completed/ }))
        fireEvent.click(await screen.findByRole('button', { name: 'Run pipeline again' }))
        fireEvent.click(await screen.findByRole('button', { name: 'Run again' }))

        await waitFor(() => expect(rerunPhotoId).toBe('8'))
    })
})
