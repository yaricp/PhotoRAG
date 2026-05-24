import React, { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { MODELS, formatSizeMB } from './models'

interface Props {
    selectedModels: Set<string>
    onDone: () => void
}

interface ModelProgress {
    percent: number
    bytes: number
}

export function StepDownloading({ selectedModels, onDone }: Props) {
    const { t } = useTranslation()
    const models = MODELS.filter(m => selectedModels.has(m.id))
    const [progress, setProgress] = useState<Record<string, ModelProgress>>({})
    const [cancelled, setCancelled] = useState(false)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        window.electronAPI.onDownloadModelProgress(({ modelId, percent, bytes }) => {
            setProgress(prev => ({ ...prev, [modelId]: { percent, bytes } }))
        })

        const run = async () => {
            try {
                for (const model of models) {
                    await window.electronAPI.downloadModel({ modelId: model.id })
                }
                onDone()
            } catch (e) {
                if (!cancelled) setError(String(e))
            }
        }
        run()
    }, []) // eslint-disable-line react-hooks/exhaustive-deps

    const handleCancel = () => {
        setCancelled(true)
        window.electronAPI.cancelDownload()
    }

    return (
        <div className="wizard-step">
            <h2>{t('wizard.stepDownloading.title')}</h2>

            {models.map(model => {
                const p = progress[model.id]
                const percent = p?.percent ?? 0
                const bytes = p?.bytes ?? 0
                return (
                    <div key={model.id} className="wizard-model-progress">
                        <div className="wizard-model-progress__header">
                            <span>{model.name}</span>
                            <span>{percent}% — {formatSizeMB(Math.round(bytes / 1_048_576))}</span>
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

            {!cancelled && (
                <div className="wizard-actions">
                    <button className="wizard-btn wizard-btn--secondary" onClick={handleCancel}>
                        {t('wizard.stepDownloading.cancelButton')}
                    </button>
                </div>
            )}
        </div>
    )
}
