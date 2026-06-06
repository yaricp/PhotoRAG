import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { ServerIcon, CloudIcon } from '@heroicons/react/24/outline'
import { PrivacyWarning } from '@/components/ui/PrivacyWarning'

interface ModelConfig {
    id: number
    type: string
    mode: 'local' | 'remote'
    model_name: string
    url?: string
    api_key?: string
    model_provider?: string
    similarity_limit?: number
}

const PREFERRED_ORDER = ['vision', 'clip', 'ocr', 'embedding', 'translator', 'chat']

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
    ollama: {
        chat:       ['llama3.2', 'llama3.1', 'mistral', 'gemma3', 'phi4'],
        vision:     ['llava', 'llava-llama3', 'moondream'],
        ocr:        ['llava', 'llava-llama3'],
        clip:       ['llava', 'llava-llama3'],
        translator: ['llama3.2', 'mistral'],
    },
}

function getSuggestions(provider: string, modelType: string): string[] {
    return MODEL_SUGGESTIONS[provider]?.[modelType] ?? []
}

interface Props {
    onDone: (configs: ModelConfig[]) => void
}

export function StepModelConfig({ onDone }: Props) {
    const { t } = useTranslation()
    const [configs, setConfigs] = useState<ModelConfig[]>([])
    const [loading, setLoading] = useState(true)
    const [saving, setSaving] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const MODEL_LABELS: Record<string, string> = {
        vision:     t('wizard.stepModelConfig.labelVision'),
        clip:       t('wizard.stepModelConfig.labelClip'),
        ocr:        t('wizard.stepModelConfig.labelOcr'),
        embedding:  t('wizard.stepModelConfig.labelEmbedding'),
        translator: t('wizard.stepModelConfig.labelTranslator'),
        chat:       t('wizard.stepModelConfig.labelChat'),
    }

    useEffect(() => {
        window.electronAPI.getModelConfigs()
            .then(data => {
                const sorted = [...data].sort((a, b) => {
                    const ia = PREFERRED_ORDER.indexOf(a.type)
                    const ib = PREFERRED_ORDER.indexOf(b.type)
                    return (ia === -1 ? 999 : ia) - (ib === -1 ? 999 : ib)
                })
                setConfigs(sorted as ModelConfig[])
                setLoading(false)
            })
            .catch(e => { setError(String(e)); setLoading(false) })
    }, [])

    const handleChange = (type: string, field: keyof ModelConfig, value: string) => {
        setConfigs(prev => prev.map(c => {
            if (c.type !== type) return c
            if (field === 'similarity_limit') {
                const num = parseFloat(value)
                return { ...c, similarity_limit: isNaN(num) ? undefined : num }
            }
            return { ...c, [field]: value }
        }))
    }

    const handleContinue = async () => {
        setSaving(true)
        try {
            await window.electronAPI.saveModelConfigs(configs)
            onDone(configs)
        } catch (e) {
            setError(String(e))
            setSaving(false)
        }
    }

    if (loading) {
        return (
            <div className="wizard-step wizard-step--wide">
                <div className="wizard-spinner" />
                <p>{t('wizard.stepModelConfig.loadingModels')}</p>
            </div>
        )
    }

    return (
        <div className="wizard-step wizard-step--wide">
            <h2>{t('wizard.stepModelConfig.title')}</h2>
            <p className="wizard-subtitle">
                {t('wizard.stepModelConfig.subtitle')}
            </p>

            {error && <div className="models-page__error">{error}</div>}

            <div className="wizard-model-config-layout">
            <div className="wizard-model-config-list">
                {configs.map(config => (
                    <div key={config.id} className="model-card">
                        <div className="model-card__header">
                            <h2 className="model-card__title">
                                {config.mode === 'local'
                                    ? <ServerIcon className="model-card__icon model-card__icon--local" />
                                    : <CloudIcon  className="model-card__icon model-card__icon--remote" />
                                }
                                {MODEL_LABELS[config.type] ?? config.type}
                            </h2>
                            <span className={`model-card__badge model-card__badge--${config.mode}`}>
                                {config.mode === 'local'
                                    ? t('wizard.stepModelConfig.localMode')
                                    : t('wizard.stepModelConfig.remoteMode')}
                            </span>
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
                                        : t('wizard.stepModelConfig.remotePlaceholder')
                                    }
                                />
                                {config.mode === 'remote' && config.model_provider && (() => {
                                    const suggestions = getSuggestions(config.model_provider, config.type)
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
                                })()}
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
                                        {config.type === 'clip' && config.mode === 'remote' && (
                                            <p className="model-field__hint">
                                                {t('wizard.stepModelConfig.remoteClipHint')}
                                            </p>
                                        )}
                                        {config.model_provider === 'deepl' && (
                                            <p className="model-field__hint">{t('wizard.stepModelConfig.deepLHint')}</p>
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
                                    placeholder="auto (scaled by dimension)"
                                />
                                <p className="model-field__hint">
                                    {t('wizard.stepModelConfig.similarityHint')}
                                </p>
                            </div>
                        )}
                    </div>
                ))}
            </div>
            <PrivacyWarning />
            </div>

            <div className="wizard-actions">
                <button
                    className="wizard-btn wizard-btn--primary"
                    onClick={handleContinue}
                    disabled={saving}
                >
                    {saving ? t('wizard.stepModelConfig.saving') : t('wizard.stepModelConfig.continueButton')}
                </button>
            </div>
        </div>
    )
}
