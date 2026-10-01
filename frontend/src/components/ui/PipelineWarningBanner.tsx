import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { getModelConfigs, getSystemStatus, MODEL_CONFIGS_CHANGED_EVENT } from '../../api/client'
import type { AIModelConfig, ModelStatus } from '../../types/api'
import './PipelineWarningBanner.css'

const PIPELINE_MODELS = ['vision', 'clip', 'ocr', 'embedding', 'translator'] as const
type PipelineModel = typeof PIPELINE_MODELS[number]

const MODEL_LABEL_KEYS: Record<PipelineModel, string> = {
    vision: 'pipelineWarning.models.vision',
    clip: 'pipelineWarning.models.clip',
    ocr: 'pipelineWarning.models.ocr',
    embedding: 'pipelineWarning.models.embedding',
    translator: 'pipelineWarning.models.translator',
}

const KEYLESS_PROVIDERS = new Set(['ollama'])
const REFRESH_INTERVAL_MS = 5000

interface PipelineWarnings {
    unconfigured: PipelineModel[]
    unavailable: PipelineModel[]
}

function evaluatePipelineWarnings(
    configs: AIModelConfig[],
    statuses: ModelStatus[],
): PipelineWarnings {
    const configByType = new Map(configs.map(config => [config.type, config]))
    const statusByName = new Map(statuses.map(status => [status.name, status]))
    const unconfigured: PipelineModel[] = []
    const unavailable: PipelineModel[] = []

    for (const type of PIPELINE_MODELS) {
        const config = configByType.get(type)
        if (!config || !config.model_name.trim() || (
            config.mode === 'remote'
            && !KEYLESS_PROVIDERS.has(config.model_provider ?? '')
            && !config.api_key?.trim()
        )) {
            unconfigured.push(type)
            continue
        }

        // ModelState reports local worker/runtime failures. Remote provider health
        // is not represented there, so do not treat stale local states as remote errors.
        if (config.mode === 'local' && statusByName.get(type)?.status === 'error') {
            unavailable.push(type)
        }
    }

    return { unconfigured, unavailable }
}

export function PipelineWarningBanner() {
    const { t } = useTranslation()
    const [warnings, setWarnings] = useState<PipelineWarnings>({ unconfigured: [], unavailable: [] })
    const [dismissedKey, setDismissedKey] = useState<string | null>(null)
    const warningKey = JSON.stringify(warnings)

    useEffect(() => {
        let active = true
        let refreshing = false

        const refresh = async () => {
            if (refreshing) return
            refreshing = true
            try {
                const [configs, systemStatus] = await Promise.all([getModelConfigs(), getSystemStatus()])
                if (active) setWarnings(evaluatePipelineWarnings(configs, systemStatus.models))
            } catch {
                // Keep the last known warning when the backend is briefly unreachable.
            } finally {
                refreshing = false
            }
        }

        const handleConfigChange = () => { void refresh() }
        void refresh()
        const interval = window.setInterval(() => { void refresh() }, REFRESH_INTERVAL_MS)
        window.addEventListener(MODEL_CONFIGS_CHANGED_EVENT, handleConfigChange)

        return () => {
            active = false
            window.clearInterval(interval)
            window.removeEventListener(MODEL_CONFIGS_CHANGED_EVENT, handleConfigChange)
        }
    }, [])

    useEffect(() => {
        if (warnings.unconfigured.length === 0 && warnings.unavailable.length === 0) {
            setDismissedKey(null)
        }
    }, [warningKey, warnings.unconfigured.length, warnings.unavailable.length])

    if ((warnings.unconfigured.length === 0 && warnings.unavailable.length === 0) || dismissedKey === warningKey) {
        return null
    }

    const formatModels = (models: PipelineModel[]) => models.map(type => t(MODEL_LABEL_KEYS[type])).join(', ')

    return (
        <div className="pipeline-warning-banner" role="alert">
            <span className="pipeline-warning-banner__icon">⚠</span>
            <div className="pipeline-warning-banner__text">
                {warnings.unconfigured.length > 0 && (
                    <p>
                        <strong>{t('pipelineWarning.missingTitle')}</strong>{' '}
                        {formatModels(warnings.unconfigured)}.{' '}
                        {t('pipelineWarning.missingAction')}
                    </p>
                )}
                {warnings.unavailable.length > 0 && (
                    <p>
                        <strong>{t('pipelineWarning.unavailableTitle')}</strong>{' '}
                        {formatModels(warnings.unavailable)}.{' '}
                        {t('pipelineWarning.unavailableAction')}
                    </p>
                )}
            </div>
            <button
                className="pipeline-warning-banner__dismiss"
                onClick={() => setDismissedKey(warningKey)}
                aria-label={t('pipelineWarning.dismiss')}
            >
                ✕
            </button>
        </div>
    )
}
