import { useState, useEffect, useRef, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { getModelConfigs, updateModelConfig, getSystemStatus } from '@/api/client'
import type { AIModelConfig } from '@/types/api'
import { ServerIcon, CloudIcon } from '@heroicons/react/24/outline'
import { Spinner } from '@/components/ui/Spinner'
import { PrivacyWarning } from '@/components/ui/PrivacyWarning'
import './ModelsPage.css'

type ModelStatusMap = Record<string, string>  // model type → status

// provider → model type → suggested model names
const MODEL_SUGGESTIONS: Record<string, Record<string, string[]>> = {
    openai: {
        chat:       ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo'],
        vision:     ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo'],
        ocr:        ['gpt-4o', 'gpt-4o-mini'],
        clip:       ['gpt-4o-mini', 'gpt-4o'],
        translator: ['gpt-4o-mini', 'gpt-4o'],
        embedding:  ['text-embedding-3-small', 'text-embedding-3-large', 'text-embedding-ada-002'],
    },
    anthropic: {
        chat:       ['claude-opus-4-5', 'claude-sonnet-4-5', 'claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022'],
        vision:     ['claude-opus-4-5', 'claude-sonnet-4-5', 'claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022'],
        ocr:        ['claude-3-5-haiku-20241022', 'claude-sonnet-4-5'],
        clip:       ['claude-3-5-haiku-20241022', 'claude-sonnet-4-5'],
        translator: ['claude-3-5-haiku-20241022', 'claude-sonnet-4-5'],
    },
    google_genai: {
        chat:       ['gemini-2.0-flash', 'gemini-2.0-flash-lite', 'gemini-1.5-flash-latest', 'gemini-1.5-pro-latest'],
        vision:     ['gemini-2.0-flash', 'gemini-1.5-flash-latest', 'gemini-1.5-pro-latest'],
        ocr:        ['gemini-2.0-flash', 'gemini-1.5-flash-latest'],
        clip:       ['gemini-2.0-flash', 'gemini-1.5-flash-latest'],
        translator: ['gemini-2.0-flash', 'gemini-1.5-flash-latest'],
    },
    google_vertexai: {
        chat:       ['gemini-2.0-flash-001', 'gemini-1.5-pro-001', 'gemini-1.5-flash-001'],
    },
    groq: {
        chat:       ['llama-3.3-70b-versatile', 'llama-3.1-8b-instant', 'mixtral-8x7b-32768', 'gemma2-9b-it'],
    },
    mistralai: {
        chat:       ['mistral-large-latest', 'mistral-small-latest', 'open-mistral-7b'],
    },
    cohere: {
        chat:       ['command-r-plus', 'command-r', 'command-light'],
    },
    together: {
        chat:       ['meta-llama/Llama-3.3-70B-Instruct-Turbo', 'mistralai/Mixtral-8x7B-Instruct-v0.1', 'meta-llama/Llama-3.2-11B-Vision-Instruct-Turbo'],
    },
    ollama: {
        chat:       ['llama3.2', 'llama3.1', 'mistral', 'gemma3', 'phi4'],
        vision:     ['llava', 'llava-llama3', 'moondream'],
        ocr:        ['llava', 'llava-llama3'],
        clip:       ['llava', 'llava-llama3'],
        translator: ['llama3.2', 'mistral'],
    },
}

function getModelSuggestions(provider: string, modelType: string): string[] {
    return MODEL_SUGGESTIONS[provider]?.[modelType] ?? []
}

// Maps API model type to wizard label key
const MODEL_TYPE_LABEL_KEY: Record<string, string> = {
    vision:     'wizard.stepModelConfig.labelVision',
    clip:       'wizard.stepModelConfig.labelClip',
    ocr:        'wizard.stepModelConfig.labelOcr',
    embedding:  'wizard.stepModelConfig.labelEmbedding',
    translator: 'wizard.stepModelConfig.labelTranslator',
    chat:       'wizard.stepModelConfig.labelChat',
}

function ModelStatusBadge({ status }: { status: string | undefined }) {
    const { t } = useTranslation()
    if (!status || status === 'ready') return null
    const label = t(`models.status.${status}`, { defaultValue: status })
    return (
        <span className={`model-status-badge model-status-badge--${status}`}>
            {(status === 'loading' || status === 'downloading') && (
                <svg className="model-status-badge__spinner" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.25" />
                    <path fill="currentColor" opacity="0.75" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
            )}
            {label}
        </span>
    )
}

export function ModelsPage() {
    const { t } = useTranslation()
    const [configs, setConfigs] = useState<AIModelConfig[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [saving, setSaving] = useState<string | null>(null)
    const [savedType, setSavedType] = useState<string | null>(null)
    const [modelStatuses, setModelStatuses] = useState<ModelStatusMap>({})
    const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

    const fetchStatuses = useCallback(() => {
        getSystemStatus().then(s => {
            const map: ModelStatusMap = {}
            s.models.forEach(m => { map[m.name] = m.status })
            setModelStatuses(map)
            // stop polling when nothing is actively loading
            const busy = s.models.some(m => m.status === 'loading')
            if (!busy && pollRef.current) {
                clearInterval(pollRef.current)
                pollRef.current = null
            }
        }).catch(() => {})
    }, [])

    const startPolling = useCallback(() => {
        if (pollRef.current) return
        fetchStatuses()
        pollRef.current = setInterval(fetchStatuses, 3000)
    }, [fetchStatuses])

    useEffect(() => {
        getModelConfigs()
            .then(data => { setConfigs(data); setError(null) })
            .catch(err => setError(err.message || t('models.error')))
            .finally(() => setLoading(false))
        startPolling()
        return () => { if (pollRef.current) clearInterval(pollRef.current) }
    }, [startPolling])

    const handleSave = async (config: AIModelConfig) => {
        setSaving(config.type)
        try {
            const updated = await updateModelConfig(config.type, {
                mode: config.mode,
                model_name: config.model_name,
                url: config.url || undefined,
                api_key: config.api_key || undefined,
                model_provider: config.model_provider || undefined,
                similarity_limit: config.similarity_limit ?? undefined,
            })
            setConfigs(prev => prev.map(c => c.type === updated.type ? updated : c))
            setSavedType(config.type)
            if (config.mode === 'local') startPolling()
        } catch (err: any) {
            setError(err.message || t('models.errorSaving'))
        } finally {
            setSaving(null)
        }
    }

    const handleChange = (type: string, field: keyof AIModelConfig, value: string) => {
        setConfigs(prev => prev.map(c => {
            if (c.type !== type) return c
            if (field === 'similarity_limit') {
                const num = parseFloat(value)
                return { ...c, similarity_limit: isNaN(num) ? undefined : num }
            }
            return { ...c, [field]: value }
        }))
    }

    if (loading) return (
        <div className="models-page models-page--loading">
            <Spinner size="lg" />
            <p className="models-page__loading-text">{t('models.loading')}</p>
        </div>
    )

    return (
        <div className="models-page">
            <h1 className="page-title">{t('models.title')}</h1>
            <p className="models-page__desc">{t('models.desc')}</p>

            {error && <div className="models-page__error">{error}</div>}

            <div className="models-page__layout">

            {savedType && (
                <div className="model-modal-overlay" onClick={() => setSavedType(null)}>
                    <div className="model-modal" onClick={e => e.stopPropagation()}>
                        <div className="model-modal__icon">✅</div>
                        <p className="model-modal__title">{t('models.configSaved')}</p>
                        <div className="model-modal__body">
                            <div className="model-modal__row">
                                <span className="model-modal__row-icon">🔄</span>
                                <span>
                                    {t(`wizard.stepModelConfig.label${savedType.charAt(0).toUpperCase()}${savedType.slice(1)}`, { defaultValue: savedType })}{' '}
                                    {configs.find(c => c.type === savedType)?.mode === 'local'
                                        ? t('models.modelLoading')
                                        : t('models.modelRemote')}
                                </span>
                            </div>
                            {savedType === 'embedding' && (
                                <div className="model-modal__row">
                                    <span className="model-modal__row-icon">🗂️</span>
                                    <span>{t('models.reindexNeeded')}</span>
                                </div>
                            )}
                        </div>
                        <div className="model-modal__footer">
                            <button className="model-modal__ok-btn" onClick={() => setSavedType(null)}>
                                {t('models.gotIt')}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            <div className="models-grid">
                {configs.map(config => (
                    <div key={config.id} className="model-card">
                        <div className="model-card__header">
                            <h2 className="model-card__title">
                                {config.mode === 'local'
                                    ? <ServerIcon className="model-card__icon model-card__icon--local" />
                                    : <CloudIcon  className="model-card__icon model-card__icon--remote" />
                                }
                                {t(MODEL_TYPE_LABEL_KEY[config.type] ?? '', { defaultValue: config.type })}
                            </h2>
                            <div className="model-card__badges">
                                <span className={`model-card__badge model-card__badge--${config.mode}`}>
                                    {config.mode === 'local' ? t('models.local') : t('models.remote')}
                                </span>
                                {config.mode === 'local' && (
                                    <ModelStatusBadge status={modelStatuses[config.type]} />
                                )}
                            </div>
                        </div>

                        <div className="model-card__form">
                            <div className="model-field">
                                <label className="model-field__label">{t('wizard.stepModelConfig.processingMode')}</label>
                                <select
                                    className="model-field__select"
                                    value={config.mode}
                                    onChange={e => handleChange(config.type, 'mode', e.target.value)}
                                >
                                    <option value="local">{t('wizard.stepModelConfig.localMode')}</option>
                                    <option value="remote">{t('wizard.stepModelConfig.remoteMode')}</option>
                                </select>
                            </div>

                            <div className="model-field">
                                <label className="model-field__label">{t('wizard.stepModelConfig.modelName')}</label>
                                <input
                                    className="model-field__input"
                                    value={config.model_name}
                                    onChange={e => handleChange(config.type, 'model_name', e.target.value)}
                                    placeholder={config.mode === 'local'
                                        ? t('wizard.stepModelConfig.localPlaceholder')
                                        : config.type === 'vision' || config.type === 'clip' || config.type === 'ocr'
                                            ? 'e.g. gpt-4o  /  claude-3-haiku-20240307  /  llava'
                                            : config.type === 'translator'
                                                ? 'e.g. gpt-4o-mini  (not needed for deepl/libretranslate)'
                                                : t('wizard.stepModelConfig.remotePlaceholder')
                                    }
                                />
                                {config.mode === 'remote' && config.model_provider && (
                                    (() => {
                                        const suggestions = getModelSuggestions(config.model_provider, config.type)
                                        if (!suggestions.length) return null
                                        return (
                                            <div className="model-suggestions">
                                                <span className="model-suggestions__label">{t('wizard.stepModelConfig.suggestions')}</span>
                                                {suggestions.map(name => (
                                                    <button
                                                        key={name}
                                                        className="model-suggestions__chip"
                                                        type="button"
                                                        onClick={() => handleChange(config.type, 'model_name', name)}
                                                    >
                                                        {name}
                                                    </button>
                                                ))}
                                            </div>
                                        )
                                    })()
                                )}
                            </div>

                            {config.mode === 'remote' && (
                                <div className="model-card__remote">
                                    <div className="model-field">
                                        <label className="model-field__label">{t('wizard.stepModelConfig.provider')}</label>
                                        <select
                                            className="model-field__select"
                                            value={config.model_provider || ''}
                                            onChange={e => handleChange(config.type, 'model_provider', e.target.value)}
                                        >
                                            <option value="">{t('wizard.stepModelConfig.autoDetect')}</option>
                                            <option value="openai">OpenAI</option>
                                            {(config.type === 'chat' || config.type === 'vision' || config.type === 'clip' || config.type === 'ocr' || config.type === 'translator') && (
                                                <option value="anthropic">Anthropic (Claude)</option>
                                            )}
                                            <option value="google_genai">Google Gemini (AI Studio key)</option>
                                            {config.type === 'chat' && <option value="google_vertexai">Google Vertex AI (GCP auth)</option>}
                                            <option value="ollama">Ollama (self-hosted)</option>
                                            {config.type === 'chat' && <option value="groq">Groq</option>}
                                            {config.type === 'chat' && <option value="mistralai">Mistral AI</option>}
                                            {config.type === 'chat' && <option value="together">Together AI</option>}
                                            {config.type === 'chat' && <option value="cohere">Cohere</option>}
                                            {config.type === 'translator' && <option value="deepl">DeepL</option>}
                                            {config.type === 'translator' && <option value="libretranslate">LibreTranslate (self-hosted)</option>}
                                        </select>
                                        {config.model_provider === 'ollama' && (
                                            <p className="model-field__hint">{t('wizard.stepModelConfig.ollamaHint')}</p>
                                        )}
                                        {config.model_provider === 'google_vertexai' && (
                                            <p className="model-field__hint">
                                                Requires GCP credentials (GOOGLE_APPLICATION_CREDENTIALS). No API key field needed.
                                            </p>
                                        )}
                                        {config.type === 'clip' && config.mode === 'remote' && (
                                            <p className="model-field__hint">{t('wizard.stepModelConfig.remoteClipHint')}</p>
                                        )}
                                        {config.model_provider === 'deepl' && (
                                            <p className="model-field__hint">{t('wizard.stepModelConfig.deepLHint')}</p>
                                        )}
                                        {config.model_provider === 'libretranslate' && (
                                            <p className="model-field__hint">
                                                Self-hosted LibreTranslate. Set the base URL to your server. Model name is not used.
                                            </p>
                                        )}
                                    </div>
                                    <div className="model-field">
                                        <label className="model-field__label">
                                            {config.model_provider === 'ollama'
                                                ? t('wizard.stepModelConfig.ollamaUrl')
                                                : t('wizard.stepModelConfig.baseUrl')}
                                        </label>
                                        <input
                                            className="model-field__input"
                                            value={config.url || ''}
                                            onChange={e => handleChange(config.type, 'url', e.target.value)}
                                            placeholder={config.model_provider === 'ollama' ? 'http://localhost:11434' : 'https://api.openai.com/v1'}
                                        />
                                    </div>
                                    {config.model_provider !== 'ollama' && config.model_provider !== 'google_vertexai' && (
                                        <div className="model-field">
                                            <label className="model-field__label">{t('wizard.stepModelConfig.apiKey')}</label>
                                            <input
                                                className="model-field__input"
                                                type="password"
                                                value={config.api_key || ''}
                                                onChange={e => handleChange(config.type, 'api_key', e.target.value)}
                                                placeholder="sk-…"
                                            />
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>

                        {config.type === 'embedding' && (
                            <div className="model-field">
                                <label className="model-field__label">{t('wizard.stepModelConfig.similarityThreshold')}</label>
                                <input
                                    className="model-field__input"
                                    type="number"
                                    step="0.01"
                                    min="0.1"
                                    max="2.0"
                                    value={config.similarity_limit ?? ''}
                                    onChange={e => handleChange(config.type, 'similarity_limit', e.target.value)}
                                    placeholder={t('wizard.stepModelConfig.similarityHint').substring(0, 30)}
                                />
                                <p className="model-field__hint">{t('wizard.stepModelConfig.similarityHint')}</p>
                            </div>
                        )}

                        <div className="model-card__footer">
                            <button
                                className="model-card__save-btn"
                                onClick={() => handleSave(config)}
                                disabled={saving === config.type}
                            >
                                {saving === config.type ? (
                                    <>
                                        <svg className="model-card__spinner" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                            <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" opacity="0.25" />
                                            <path fill="currentColor" opacity="0.75" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                        </svg>
                                        {t('models.saving')}
                                    </>
                                ) : t('models.save')}
                            </button>
                        </div>
                    </div>
                ))}
            </div>
                <PrivacyWarning />
            </div>
        </div>
    )
}
