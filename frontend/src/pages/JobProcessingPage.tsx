import React, { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { getActivePipelineTasks, getRecentPipelineTasks, retryPipelineTask, runPipelineForPhoto } from '@/api/client'
import { Spinner } from '@/components/ui/Spinner'
import { ConfirmModal } from '@/components/ui/ConfirmModal'
import type { PipelineTask } from '@/types/api'
import './JobProcessingPage.css'

const STATUS_ICON: Record<string, string> = {
    pending: '⏳',
    running: '🔄',
    done: '✅',
    failed: '❌',
}

function shortName(task_name: string): string {
    return task_name.replace(/_task$/, '').replace(/_/g, ' ')
}

function parseUtc(ts: string): Date {
    // SQLAlchemy returns naive UTC strings like "2026-05-14T11:30:00".
    // Without a timezone marker JS treats them as local time, adding/subtracting
    // the user's UTC offset. Appending 'Z' forces correct UTC interpretation.
    const marked = ts.endsWith('Z') || ts.includes('+') ? ts : ts + 'Z'
    return new Date(marked)
}

function formatElapsed(started_at: string | null, now: number): string {
    if (!started_at) return ''
    const secs = Math.max(0, Math.round((now - parseUtc(started_at).getTime()) / 1000))
    if (secs < 60) return `${secs}s`
    const m = Math.floor(secs / 60)
    const s = secs % 60
    return `${m}m ${s < 10 ? '0' : ''}${s}s`
}

type PhotoGroup = { photo_id: number; tasks: PipelineTask[] }

function groupByPhoto(tasks: PipelineTask[]): PhotoGroup[] {
    const map = new Map<number, PipelineTask[]>()
    for (const t of tasks) {
        if (!map.has(t.photo_id)) map.set(t.photo_id, [])
        map.get(t.photo_id)!.push(t)
    }
    return Array.from(map.entries())
        .map(([photo_id, tasks]) => ({ photo_id, tasks }))
        .sort((a, b) => b.photo_id - a.photo_id)
}

function PhaseBlock({
    phase,
    tasks,
    now,
    busyTaskId,
    onRetryTask,
}: {
    phase: string
    tasks: PipelineTask[]
    now: number
    busyTaskId: number | null
    onRetryTask: (task: PipelineTask) => void
}) {
    const { t } = useTranslation()
    return (
        <div className="phase-block">
            <div className="phase-block__label">{phase.replace('_', ' ')}</div>
            <div className="phase-block__tasks">
                {tasks.map(task => (
                    <div
                        key={task.id}
                        className={`task-chip task-chip--${task.status}`}
                        title={task.error ?? task.task_name}
                    >
                        <span className="task-chip__icon">{STATUS_ICON[task.status] ?? '?'}</span>
                        <span className="task-chip__name">{shortName(task.task_name)}</span>
                        {task.status === 'running' && task.started_at && (
                            <span className="task-chip__elapsed">{formatElapsed(task.started_at, now)}</span>
                        )}
                        {task.status === 'failed' && (
                            <button
                                type="button"
                                className="task-chip__retry"
                                onClick={() => onRetryTask(task)}
                                disabled={busyTaskId === task.id}
                                title={t('processing.retryTask')}
                            >
                                {busyTaskId === task.id ? '…' : t('processing.retryTask')}
                            </button>
                        )}
                    </div>
                ))}
            </div>
        </div>
    )
}

function PhotoRow({
    photo_id,
    tasks,
    now,
    busyTaskId,
    busyPhotoId,
    onRetryTask,
    onRunPipeline,
}: PhotoGroup & {
    now: number
    busyTaskId: number | null
    busyPhotoId: number | null
    onRetryTask: (task: PipelineTask) => void
    onRunPipeline: (photoId: number) => void
}) {
    const { t } = useTranslation()
    const phases = Array.from(new Set(tasks.map(t => t.phase))).sort()
    const overallStatus = tasks.some(t => t.status === 'running')
        ? 'running'
        : tasks.some(t => t.status === 'failed')
        ? 'failed'
        : tasks.every(t => t.status === 'done')
        ? 'done'
        : 'pending'

    return (
        <div className={`photo-row photo-row--${overallStatus}`}>
            <div className="photo-row__header">
                <span className="photo-row__id">Photo #{photo_id}</span>
                <div className="photo-row__header-actions">
                    {overallStatus === 'failed' && (
                        <button
                            type="button"
                            className="photo-row__rerun-btn"
                            onClick={() => onRunPipeline(photo_id)}
                            disabled={busyPhotoId === photo_id}
                        >
                            {busyPhotoId === photo_id ? t('processing.starting') : t('processing.rerunPipeline')}
                        </button>
                    )}
                    <span className={`photo-row__status photo-row__status--${overallStatus}`}>
                        {STATUS_ICON[overallStatus]} {overallStatus}
                    </span>
                </div>
            </div>
            <div className="photo-row__phases">
                {phases.map(phase => (
                    <PhaseBlock
                        key={phase}
                        phase={phase}
                        tasks={tasks.filter(t => t.phase === phase)}
                        now={now}
                        busyTaskId={busyTaskId}
                        onRetryTask={onRetryTask}
                    />
                ))}
            </div>
        </div>
    )
}

export function JobProcessingPage() {
    const { t } = useTranslation()
    const [active, setActive] = useState<PipelineTask[]>([])
    const [recent, setRecent] = useState<PipelineTask[]>([])
    const [loading, setLoading] = useState(true)
    const [now, setNow] = useState(Date.now())
    const [busyTaskId, setBusyTaskId] = useState<number | null>(null)
    const [busyPhotoId, setBusyPhotoId] = useState<number | null>(null)
    const [pendingRerunPhotoId, setPendingRerunPhotoId] = useState<number | null>(null)
    const [actionError, setActionError] = useState<string | null>(null)

    const loadData = async () => {
        try {
            const [activeTasks, recentTasks] = await Promise.all([
                getActivePipelineTasks(),
                getRecentPipelineTasks(50),
            ])
            setActive(activeTasks)
            setRecent(recentTasks)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        loadData()
        const poll = setInterval(loadData, 3000)
        const tick = setInterval(() => setNow(Date.now()), 1000)
        return () => {
            clearInterval(poll)
            clearInterval(tick)
        }
    }, [])

    async function handleRetryTask(task: PipelineTask) {
        setActionError(null)
        setBusyTaskId(task.id)
        try {
            await retryPipelineTask(task.id)
            await loadData()
        } catch (err) {
            setActionError(err instanceof Error ? err.message : String(err))
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
        } catch (err) {
            setActionError(err instanceof Error ? err.message : String(err))
        } finally {
            setBusyPhotoId(null)
        }
    }

    const activeGroups = groupByPhoto(active)
    const activeTaskIds = new Set(active.map(t => t.id))
    const recentGroups = groupByPhoto(recent.filter(t => !activeTaskIds.has(t.id)))

    return (
        <div className="jobs-page">
            <div className="jobs-page__header">
                <span>{activeGroups.length !== 1
                    ? t('processing.activeCountPlural', { count: activeGroups.length })
                    : t('processing.activeCount', { count: activeGroups.length })}</span>
            </div>

            {actionError && <div className="jobs-page__error">{actionError}</div>}

            {loading && (
                <div className="jobs-page__center">
                    <Spinner size="lg" />
                </div>
            )}

            {!loading && (
                <>
                    {activeGroups.length > 0 ? (
                        <section className="pipeline-section">
                            <h3 className="pipeline-section__title">{t('processing.active')}</h3>
                            {activeGroups.map(g => (
                                <PhotoRow
                                    key={g.photo_id}
                                    {...g}
                                    now={now}
                                    busyTaskId={busyTaskId}
                                    busyPhotoId={busyPhotoId}
                                    onRetryTask={handleRetryTask}
                                    onRunPipeline={setPendingRerunPhotoId}
                                />
                            ))}
                        </section>
                    ) : (
                        <div className="jobs-page__center">{t('processing.noActive')}</div>
                    )}

                    {recentGroups.length > 0 && (
                        <section className="pipeline-section pipeline-section--recent">
                            <h3 className="pipeline-section__title">{t('processing.recent')}</h3>
                            {recentGroups.map(g => (
                                <PhotoRow
                                    key={g.photo_id}
                                    {...g}
                                    now={now}
                                    busyTaskId={busyTaskId}
                                    busyPhotoId={busyPhotoId}
                                    onRetryTask={handleRetryTask}
                                    onRunPipeline={setPendingRerunPhotoId}
                                />
                            ))}
                        </section>
                    )}
                </>
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
