import React, { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
    getPipelineRuns,
    resumePipelineRun,
    retryPipelineTask,
    runPipelineForPhoto,
} from '@/api/client'
import { Spinner } from '@/components/ui/Spinner'
import { ConfirmModal } from '@/components/ui/ConfirmModal'
import type { PipelineRun, PipelineRunBucket, PipelineRunTask } from '@/types/api'
import './JobProcessingPage.css'

const PAGE_SIZE = 20

const TASK_STATUS_ICON: Record<string, string> = {
    pending: '⏳',
    running: '🔄',
    done: '✅',
    failed: '❌',
    skipped: '⚠️',
    paused: '⏸️',
    interrupted: '⏹️',
}

const RUN_STATUS_ICON: Record<string, string> = {
    queued: '⏳',
    running: '🔄',
    completed: '✅',
    'completed-with-errors': '⚠️',
    paused: '⏸️',
    interrupted: '⏹️',
}

const RUN_STATUS_KEY: Record<string, string> = {
    queued: 'queued',
    running: 'running',
    completed: 'completed',
    'completed-with-errors': 'completedWithErrors',
    paused: 'paused',
    interrupted: 'interrupted',
}

function shortName(taskName: string): string {
    return taskName.replace(/_task$/, '').replace(/_/g, ' ')
}

function parseUtc(timestamp: string): Date {
    const marked = /(?:Z|[+-]\d{2}:\d{2})$/i.test(timestamp) ? timestamp : `${timestamp}Z`
    return new Date(marked)
}

function formatElapsed(startedAt: string | null, now: number): string {
    if (!startedAt) return ''
    const timestamp = parseUtc(startedAt).getTime()
    if (Number.isNaN(timestamp)) return ''
    const seconds = Math.max(0, Math.round((now - timestamp) / 1000))
    if (seconds < 60) return `${seconds}s`
    const minutes = Math.floor(seconds / 60)
    const remainder = seconds % 60
    return `${minutes}m ${remainder < 10 ? '0' : ''}${remainder}s`
}

function formatWait(seconds: number): string {
    const rounded = Math.max(0, Math.round(seconds))
    if (rounded < 60) return `${rounded}s`
    const minutes = Math.floor(rounded / 60)
    const remainder = rounded % 60
    return `${minutes}m ${remainder < 10 ? '0' : ''}${remainder}s`
}

function formatTimestamp(timestamp: string, locale: string): string {
    const date = parseUtc(timestamp)
    return Number.isNaN(date.getTime()) ? '' : date.toLocaleString(locale)
}

function PhaseBlock({
    phase,
    tasks,
    now,
    busyTaskId,
    onRetryTask,
}: {
    phase: string
    tasks: PipelineRunTask[]
    now: number
    busyTaskId: number | null
    onRetryTask: (task: PipelineRunTask) => void
}) {
    const { t } = useTranslation()
    return (
        <div className="phase-block">
            <div className="phase-block__label">{phase.replace('_', ' ')}</div>
            <div className="phase-block__tasks">
                {tasks.map(task => (
                    <div key={task.id} className={`task-chip task-chip--${task.status}`}>
                        <div className="task-chip__main" title={task.error ?? task.skip_reason ?? task.task_name}>
                            <span className="task-chip__icon">{TASK_STATUS_ICON[task.status] ?? '?'}</span>
                            <span className="task-chip__name">{shortName(task.task_name)}</span>
                            <span className="task-chip__attempt">{t('processing.attempt', { count: task.attempt })}</span>
                            {task.status === 'running' && task.started_at && (
                                <span className="task-chip__elapsed">{formatElapsed(task.started_at, now)}</span>
                            )}
                            {task.status === 'failed' && (
                                <button
                                    type="button"
                                    className="task-chip__retry"
                                    onClick={() => onRetryTask(task)}
                                    disabled={busyTaskId === task.id}
                                >
                                    {busyTaskId === task.id ? '…' : t('processing.retryTask')}
                                </button>
                            )}
                        </div>
                        {task.error && <div className="task-chip__detail">{task.error}</div>}
                        {task.skip_reason && <div className="task-chip__detail">{task.skip_reason}</div>}
                    </div>
                ))}
            </div>
        </div>
    )
}

function RunCard({
    run,
    now,
    locale,
    busyTaskId,
    busyPhotoId,
    busyRunId,
    onRetryTask,
    onRunPipeline,
    onResumeRun,
}: {
    run: PipelineRun
    now: number
    locale: string
    busyTaskId: number | null
    busyPhotoId: number | null
    busyRunId: number | null
    onRetryTask: (task: PipelineRunTask) => void
    onRunPipeline: (photoId: number) => void
    onResumeRun: (runId: number) => void
}) {
    const { t } = useTranslation()
    const phases = Array.from(new Set(run.tasks.map(task => task.phase))).sort()
    const statusKey = RUN_STATUS_KEY[run.status] ?? run.status
    const hasSavedOutputs = Boolean(
        run.photo.description
        || run.photo.translated_description
        || run.photo.ocr_text
        || run.photo.tags.length
        || run.photo.categories.length
    )
    const isResumable = run.status === 'paused' || run.status === 'interrupted'

    return (
        <article className={`photo-row photo-row--${run.status}`}>
            <header className="photo-row__header">
                <div className="photo-row__identity">
                    <strong className="photo-row__id">Photo #{run.photo_id}</strong>
                    <span>{t('processing.run', { id: run.run_id })}</span>
                    <span>{t('processing.source', { source: run.source })}</span>
                    <time dateTime={run.created_at}>{formatTimestamp(run.created_at, locale)}</time>
                </div>
                <div className="photo-row__header-actions">
                    {isResumable && (
                        <button
                            type="button"
                            className="photo-row__resume-btn"
                            onClick={() => onResumeRun(run.run_id)}
                            disabled={busyRunId === run.run_id}
                        >
                            {busyRunId === run.run_id ? t('processing.resuming') : t('processing.resumeRun')}
                        </button>
                    )}
                    <button
                        type="button"
                        className="photo-row__rerun-btn"
                        onClick={() => onRunPipeline(run.photo_id)}
                        disabled={busyPhotoId === run.photo_id}
                    >
                        {busyPhotoId === run.photo_id ? t('processing.starting') : t('processing.rerunPipeline')}
                    </button>
                    <span className={`photo-row__status photo-row__status--${run.status}`}>
                        {RUN_STATUS_ICON[run.status] ?? '?'} {t(`processing.status.${statusKey}`)}
                    </span>
                </div>
            </header>

            {run.summary && (
                <div className="photo-row__summary">
                    <strong>{t('processing.summary')}:</strong> {run.summary}
                </div>
            )}
            {run.status === 'queued' && run.queue_position !== null && (
                <div className="photo-row__queue" role="status">
                    {t('processing.queuePosition', { position: run.queue_position })}
                    {' · '}
                    {t('processing.waitTime', { duration: formatWait(run.wait_seconds) })}
                </div>
            )}

            <section className="photo-output" aria-label={t('processing.outputs')}>
                <h4>{t('processing.outputs')}</h4>
                <div className="photo-output__field">
                    <strong>{t('processing.file')}:</strong> <span>{run.photo.file_path}</span>
                </div>
                {run.photo.description && (
                    <div className="photo-output__field">
                        <strong>{t('processing.description')}:</strong> <span>{run.photo.description}</span>
                    </div>
                )}
                {run.photo.translated_description && (
                    <div className="photo-output__field">
                        <strong>{t('processing.translatedDescription')}:</strong> <span>{run.photo.translated_description}</span>
                    </div>
                )}
                {run.photo.ocr_text && (
                    <div className="photo-output__field">
                        <strong>{t('processing.ocrText')}:</strong> <span>{run.photo.ocr_text}</span>
                    </div>
                )}
                {run.photo.tags.length > 0 && (
                    <div className="photo-output__field">
                        <strong>{t('processing.tags')}:</strong> <span>{run.photo.tags.join(', ')}</span>
                    </div>
                )}
                {run.photo.categories.length > 0 && (
                    <div className="photo-output__field">
                        <strong>{t('processing.categories')}:</strong> <span>{run.photo.categories.join(', ')}</span>
                    </div>
                )}
                {!hasSavedOutputs && <p className="photo-output__empty">{t('processing.noSavedOutputs')}</p>}
            </section>

            <section className="photo-row__phases" aria-label={t('processing.taskHistory')}>
                {phases.map(phase => (
                    <PhaseBlock
                        key={phase}
                        phase={phase}
                        tasks={run.tasks.filter(task => task.phase === phase)}
                        now={now}
                        busyTaskId={busyTaskId}
                        onRetryTask={onRetryTask}
                    />
                ))}
                {run.tasks.length === 0 && <div className="jobs-page__muted">{t('processing.noTasks')}</div>}
            </section>
        </article>
    )
}

export function JobProcessingPage() {
    const { t, i18n } = useTranslation()
    const [bucket, setBucket] = useState<PipelineRunBucket>('active')
    const [page, setPage] = useState(1)
    const [data, setData] = useState<{ items: PipelineRun[]; total: number; pages: number } | null>(null)
    const [loading, setLoading] = useState(true)
    const [loadError, setLoadError] = useState(false)
    const [now, setNow] = useState(Date.now())
    const [busyTaskId, setBusyTaskId] = useState<number | null>(null)
    const [busyPhotoId, setBusyPhotoId] = useState<number | null>(null)
    const [busyRunId, setBusyRunId] = useState<number | null>(null)
    const [pendingRerunPhotoId, setPendingRerunPhotoId] = useState<number | null>(null)
    const [actionError, setActionError] = useState<string | null>(null)

    const loadData = useCallback(async () => {
        try {
            const result = await getPipelineRuns(bucket, page, PAGE_SIZE)
            setData(result)
            setLoadError(false)
        } catch {
            setLoadError(true)
        } finally {
            setLoading(false)
        }
    }, [bucket, page])

    useEffect(() => {
        setLoading(true)
        void loadData()
        const poll = setInterval(() => void loadData(), 3000)
        const tick = setInterval(() => setNow(Date.now()), 1000)
        return () => {
            clearInterval(poll)
            clearInterval(tick)
        }
    }, [loadData])

    async function handleRetryTask(task: PipelineRunTask) {
        setActionError(null)
        setBusyTaskId(task.id)
        try {
            await retryPipelineTask(task.id)
            await loadData()
        } catch (error) {
            setActionError(error instanceof Error ? error.message : String(error))
        } finally {
            setBusyTaskId(null)
        }
    }

    async function handleRunPipeline(photoId: number) {
        setActionError(null)
        setBusyPhotoId(photoId)
        try {
            await runPipelineForPhoto(photoId)
            await loadData()
        } catch (error) {
            setActionError(error instanceof Error ? error.message : String(error))
        } finally {
            setBusyPhotoId(null)
        }
    }

    async function handleResumeRun(runId: number) {
        setActionError(null)
        setBusyRunId(runId)
        try {
            await resumePipelineRun(runId)
            await loadData()
        } catch (error) {
            setActionError(error instanceof Error ? error.message : String(error))
        } finally {
            setBusyRunId(null)
        }
    }

    const total = data?.total ?? 0
    const pages = data?.pages ?? 1
    const runs = data?.items ?? []

    return (
        <div className="jobs-page">
            <div className="jobs-page__header">
                <h1>{t('processing.title')}</h1>
                {bucket === 'active' ? (
                    <span>{total !== 1
                        ? t('processing.activeCountPlural', { count: total })
                        : t('processing.activeCount', { count: total })}</span>
                ) : (
                    <span>{t('processing.completedCount', { count: total })}</span>
                )}
            </div>

            <div className="jobs-tabs" role="tablist" aria-label={t('processing.title')}>
                <button
                    type="button"
                    role="tab"
                    aria-label={t('processing.activeTab')}
                    aria-selected={bucket === 'active'}
                    className={bucket === 'active' ? 'jobs-tabs__tab jobs-tabs__tab--selected' : 'jobs-tabs__tab'}
                    onClick={() => { setBucket('active'); setPage(1) }}
                >
                    {t('processing.activeTab')} <span aria-hidden="true">{bucket === 'active' ? total : ''}</span>
                </button>
                <button
                    type="button"
                    role="tab"
                    aria-label={t('processing.completedTab')}
                    aria-selected={bucket === 'completed'}
                    className={bucket === 'completed' ? 'jobs-tabs__tab jobs-tabs__tab--selected' : 'jobs-tabs__tab'}
                    onClick={() => { setBucket('completed'); setPage(1) }}
                >
                    {t('processing.completedTab')} <span aria-hidden="true">{bucket === 'completed' ? total : ''}</span>
                </button>
            </div>

            {actionError && <div className="jobs-page__error">{actionError}</div>}
            {loadError && !loading && <div className="jobs-page__error">{t('processing.loadError')}</div>}

            {loading ? (
                <div className="jobs-page__center"><Spinner size="lg" /></div>
            ) : (
                <div role="tabpanel" className="jobs-page__runs">
                    {runs.length === 0 ? (
                        <div className="jobs-page__center">
                            {bucket === 'active' ? t('processing.noActive') : t('processing.noCompleted')}
                        </div>
                    ) : (
                        runs.map(run => (
                            <RunCard
                                key={run.run_id}
                                run={run}
                                now={now}
                                locale={i18n.language}
                                busyTaskId={busyTaskId}
                                busyPhotoId={busyPhotoId}
                                busyRunId={busyRunId}
                                onRetryTask={handleRetryTask}
                                onRunPipeline={setPendingRerunPhotoId}
                                onResumeRun={handleResumeRun}
                            />
                        ))
                    )}

                    {pages > 1 && (
                        <nav className="jobs-pagination" aria-label={t('processing.pagination')}>
                            <button type="button" disabled={page <= 1} onClick={() => setPage(current => Math.max(1, current - 1))}>
                                {t('processing.previousPage')}
                            </button>
                            <span>{t('processing.pageInfo', { page, pages })}</span>
                            <button type="button" disabled={page >= pages} onClick={() => setPage(current => current + 1)}>
                                {t('processing.nextPage')}
                            </button>
                        </nav>
                    )}
                </div>
            )}

            <ConfirmModal
                open={pendingRerunPhotoId !== null}
                title={t('processing.rerunPipelineConfirmTitle')}
                message={t('processing.rerunPipelineConfirmMessage')}
                confirmLabel={t('processing.rerunPipelineConfirm')}
                variant="warning"
                onConfirm={() => {
                    if (pendingRerunPhotoId !== null) void handleRunPipeline(pendingRerunPhotoId)
                }}
                onClose={() => setPendingRerunPhotoId(null)}
            />
        </div>
    )
}
