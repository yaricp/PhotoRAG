import React, { useEffect, useState, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { MODELS, formatSizeMB } from './models'

interface Props {
    selectedModels: Set<string>
    ollamaModels?: Array<{ name: string; url?: string }>
    onDone: () => void
    onBack?: () => void
}

interface ModelProgress {
    bytes: number
    done: boolean
}

export function StepDownloading({ selectedModels, ollamaModels = [], onDone, onBack }: Props) {
    const { t } = useTranslation()
    const models = MODELS.filter(m => selectedModels.has(m.id))
    const uniqueOllamaModels = ollamaModels.filter((model, index, all) =>
        all.findIndex(other => other.name === model.name && other.url === model.url) === index)
    const [progress, setProgress] = useState<Record<string, ModelProgress>>({})
    const [ollamaProgress, setOllamaProgress] = useState<Record<string, { status: string; total: number; completed: number; done: boolean }>>({})
    const [allDone, setAllDone] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const startedRef = useRef(false)
    const activeRef = useRef(true)
    const cancelledRef = useRef(false)

    useEffect(() => {
        activeRef.current = true
        const unsubscribeOllama = window.electronAPI.onOllamaPullProgress?.(({ model, status, total, completed, done }) => {
            setOllamaProgress(prev => ({ ...prev, [model]: { status, total, completed, done } }))
        })
        window.electronAPI.onDownloadModelProgress(({ modelId, bytes, done }) => {
            setProgress(prev => ({ ...prev, [modelId]: { bytes: bytes < 0 ? 0 : bytes, done } }))
        })

        if (startedRef.current) return () => { activeRef.current = false; unsubscribeOllama?.() }
        startedRef.current = true

        window.electronAPI.getModelStatuses().then(async (statuses: Record<string, string>) => {
            if (cancelledRef.current || !activeRef.current) return
            const readyIds = new Set(
                Object.entries(statuses)
                    .filter(([, s]) => s === 'ready')
                    .map(([id]) => id)
            )

            // Pre-fill progress for already-ready models
            const initialProgress: Record<string, ModelProgress> = {}
            for (const m of models) {
                if (readyIds.has(m.id)) initialProgress[m.id] = { bytes: 0, done: true }
            }
            if (Object.keys(initialProgress).length > 0) {
                setProgress(prev => ({ ...prev, ...initialProgress }))
            }

            const toDownload = models.filter(m => !readyIds.has(m.id))
            await Promise.all(toDownload.map(m => window.electronAPI.downloadModel({ modelId: m.id })))
            if (cancelledRef.current || !activeRef.current) return
            for (const { name, url } of uniqueOllamaModels) {
                const installed = await window.electronAPI.listOllamaModels(url)
                if (cancelledRef.current || !activeRef.current) return
                if (installed.includes(name) || installed.includes(`${name}:latest`)) {
                    setOllamaProgress(prev => ({ ...prev, [name]: { status: 'success', total: 0, completed: 0, done: true } }))
                    continue
                }
                await window.electronAPI.pullOllamaModel({ model: name, url })
                if (cancelledRef.current || !activeRef.current) return
            }
            if (activeRef.current) {
                setAllDone(true)
                onDone()
            }
        }).catch(e => { if (activeRef.current && !cancelledRef.current) setError(String(e)) })
        return () => { activeRef.current = false; unsubscribeOllama?.() }
    }, []) // eslint-disable-line react-hooks/exhaustive-deps

    const handleCancel = () => {
        cancelledRef.current = true
        window.electronAPI.cancelDownload()
        window.electronAPI.cancelOllamaPulls?.()
        setError('cancelled')
    }

    const handleBack = () => {
        activeRef.current = false
        cancelledRef.current = true
        window.electronAPI.cancelDownload()
        window.electronAPI.cancelOllamaPulls?.()
        onBack?.()
    }

    return (
        <div className="wizard-step">
            <h2>{t('wizard.stepDownloading.title')}</h2>

            {models.map(model => {
                const p = progress[model.id]
                const totalBytes = model.sizeMB * 1_048_576
                const percent = p?.done
                    ? 100
                    : totalBytes > 0
                        ? Math.min(99, Math.round(((p?.bytes ?? 0) / totalBytes) * 100))
                        : 0
                return (
                    <div key={model.id} className="wizard-model-progress">
                        <div className="wizard-model-progress__header">
                            <span>{model.name}</span>
                            <span>{percent}% — {formatSizeMB(model.sizeMB)}</span>
                        </div>
                        <div
                            role="progressbar"
                            aria-label={model.name}
                            aria-valuenow={percent}
                            aria-valuemin={0}
                            aria-valuemax={100}
                            className="wizard-progressbar"
                        >
                            <div className="wizard-progressbar__fill" style={{ width: `${percent}%` }} />
                        </div>
                    </div>
                )
            })}

            {uniqueOllamaModels.map(({ name, url }) => {
                const item = ollamaProgress[name]
                const percent = item?.done ? 100 : item?.total ? Math.min(99, Math.round(item.completed / item.total * 100)) : 0
                return <div key={`${url || 'http://localhost:11434'}/${name}`} className="wizard-model-progress">
                    <div className="wizard-model-progress__header"><span>{name}</span><span>{item?.status || ''} {item?.total ? `${percent}%` : ''}</span></div>
                    <div role="progressbar" aria-label={name} aria-valuenow={percent} aria-valuemin={0} aria-valuemax={100}
                        className={`wizard-progressbar${!item?.total && !item?.done ? ' wizard-progressbar--active' : ''}`}>
                        <div className="wizard-progressbar__fill" style={{ width: `${percent}%` }} />
                    </div>
                </div>
            })}

            {error && <p className="wizard-error">{
                error === 'cancelled' ? t('wizard.stepDownloading.cancelled')
                    : error.includes('Ollama is not available')
                    ? t('wizard.stepDownloading.ollamaUnavailable')
                    : t('wizard.stepDownloading.errorMessage', { error })
            }</p>}

            {!allDone && (
                <div className="wizard-actions">
                    {onBack && (
                        <button className="wizard-btn wizard-btn--ghost" onClick={handleBack}>
                            {t('wizard.stepDownloading.backButton')}
                        </button>
                    )}
                    <button className="wizard-btn wizard-btn--secondary" onClick={handleCancel}>
                        {t('wizard.stepDownloading.cancelButton')}
                    </button>
                </div>
            )}
        </div>
    )
}
