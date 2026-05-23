import React, { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { getActivePipelineTasks, getRecentPipelineTasks } from '@/api/client'
import { Spinner } from '@/components/ui/Spinner'
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

function PhaseBlock({ phase, tasks, now }: { phase: string; tasks: PipelineTask[]; now: number }) {
    return (
        <div className="phase-block">
            <div className="phase-block__label">{phase.replace('_', ' ')}</div>
            <div className="phase-block__tasks">
                {tasks.map(t => (
                    <div
                        key={t.id}
                        className={`task-chip task-chip--${t.status}`}
                        title={t.error ?? t.task_name}
                    >
                        <span className="task-chip__icon">{STATUS_ICON[t.status] ?? '?'}</span>
                        <span className="task-chip__name">{shortName(t.task_name)}</span>
                        {t.status === 'running' && t.started_at && (
                            <span className="task-chip__elapsed">{formatElapsed(t.started_at, now)}</span>
                        )}
                    </div>
                ))}
            </div>
        </div>
    )
}

function PhotoRow({ photo_id, tasks, now }: PhotoGroup & { now: number }) {
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
                <span className={`photo-row__status photo-row__status--${overallStatus}`}>
                    {STATUS_ICON[overallStatus]} {overallStatus}
                </span>
            </div>
            <div className="photo-row__phases">
                {phases.map(phase => (
                    <PhaseBlock
                        key={phase}
                        phase={phase}
                        tasks={tasks.filter(t => t.phase === phase)}
                        now={now}
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

    const activeGroups = groupByPhoto(active)
    const activeTaskIds = new Set(active.map(t => t.id))
    const recentGroups = groupByPhoto(recent.filter(t => !activeTaskIds.has(t.id)))

    return (
        <div className="jobs-page">
            <div className="jobs-page__header">
                <h2>{t('processing.title')}</h2>
                <span>{activeGroups.length !== 1
                    ? t('processing.activeCountPlural', { count: activeGroups.length })
                    : t('processing.activeCount', { count: activeGroups.length })}</span>
            </div>

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
                                <PhotoRow key={g.photo_id} {...g} now={now} />
                            ))}
                        </section>
                    ) : (
                        <div className="jobs-page__center">{t('processing.noActive')}</div>
                    )}

                    {recentGroups.length > 0 && (
                        <section className="pipeline-section pipeline-section--recent">
                            <h3 className="pipeline-section__title">{t('processing.recent')}</h3>
                            {recentGroups.map(g => (
                                <PhotoRow key={g.photo_id} {...g} now={now} />
                            ))}
                        </section>
                    )}
                </>
            )}
        </div>
    )
}
