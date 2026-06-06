import React, { useState, useEffect } from 'react'
import { getModelConfigs, getSystemStatus } from '../../api/client'
import { AIModelConfig, ModelStatus } from '../../types/api'
import './PipelineWarningBanner.css'

// Models used in the photo ingestion pipeline (chat is not included)
const PIPELINE_MODELS = ['vision', 'clip', 'ocr', 'embedding', 'translator'] as const
type PipelineModel = typeof PIPELINE_MODELS[number]

const MODEL_LABELS: Record<PipelineModel, string> = {
    vision:     'Vision (image description)',
    clip:       'CLIP (tagging)',
    ocr:        'OCR (text extraction)',
    embedding:  'Embedding (semantic search)',
    translator: 'Translation',
}

// Providers that work without an API key (self-hosted)
const KEYLESS_PROVIDERS = new Set(['ollama'])

function isConfigured(config: AIModelConfig, status: ModelStatus | undefined): boolean {
    if (config.mode === 'local') {
        // Local model is configured as long as it hasn't hard-failed.
        // 'loading' / 'pending' are transient startup states, not a problem.
        return status?.status !== 'error'
    }
    // Remote: needs an api_key unless it's a keyless provider like Ollama
    if (KEYLESS_PROVIDERS.has(config.model_provider ?? '')) return true
    return !!(config.api_key?.trim())
}

export function PipelineWarningBanner() {
    const [unconfigured, setUnconfigured] = useState<string[]>([])
    const [dismissed, setDismissed] = useState(false)

    useEffect(() => {
        Promise.all([getModelConfigs(), getSystemStatus()])
            .then(([configs, statusResp]) => {
                const statusMap = new Map<string, ModelStatus>(
                    statusResp.models.map(m => [m.name, m])
                )
                const missing = configs
                    .filter((c): c is AIModelConfig & { type: PipelineModel } =>
                        (PIPELINE_MODELS as readonly string[]).includes(c.type)
                    )
                    .filter(c => !isConfigured(c, statusMap.get(c.type)))
                    .map(c => MODEL_LABELS[c.type])
                setUnconfigured(missing)
            })
            .catch(() => { /* backend not yet ready, ignore */ })
    }, [])

    if (!unconfigured.length || dismissed) return null

    return (
        <div className="pipeline-warning-banner" role="alert">
            <span className="pipeline-warning-banner__icon">⚠</span>
            <span className="pipeline-warning-banner__text">
                <strong>Some pipeline steps will be skipped:</strong>
                {' '}
                {unconfigured.join(', ')}.
                {' '}
                Configure them in <strong>Settings → Models</strong>.
            </span>
            <button
                className="pipeline-warning-banner__dismiss"
                onClick={() => setDismissed(true)}
                aria-label="Dismiss warning"
            >
                ✕
            </button>
        </div>
    )
}
