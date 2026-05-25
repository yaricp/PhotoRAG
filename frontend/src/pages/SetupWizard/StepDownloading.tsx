import React, { useEffect, useState, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { MODELS, formatSizeMB } from './models'

interface Props {
    selectedModels: Set<string>
    onDone: () => void
    onBack?: () => void
}

interface ModelProgress {
    bytes: number
    done: boolean
}

export function StepDownloading({ selectedModels, onDone, onBack }: Props) {
    const { t } = useTranslation()
    const models = MODELS.filter(m => selectedModels.has(m.id))
    const [progress, setProgress] = useState<Record<string, ModelProgress>>({})
    const [allDone, setAllDone] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const startedRef = useRef(false)

    useEffect(() => {
        window.electronAPI.onDownloadModelProgress(({ modelId, bytes, done }) => {
            setProgress(prev => ({ ...prev, [modelId]: { bytes: bytes < 0 ? 0 : bytes, done } }))
        })

        if (startedRef.current) return
        startedRef.current = true

        window.electronAPI.getModelStatuses().then((statuses: Record<string, string>) => {
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
            if (toDownload.length === 0) {
                setAllDone(true)
                onDone()
                return
            }

            Promise.all(toDownload.map(m => window.electronAPI.downloadModel({ modelId: m.id })))
                .then(() => {
                    setAllDone(true)
                    onDone()
                })
                .catch(e => setError(String(e)))
        })
    }, []) // eslint-disable-line react-hooks/exhaustive-deps

    const handleCancel = () => {
        window.electronAPI.cancelDownload()
    }

    const handleBack = () => {
        window.electronAPI.cancelDownload()
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

            {error && <p className="wizard-error">{t('wizard.stepDownloading.errorMessage', { error })}</p>}

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
