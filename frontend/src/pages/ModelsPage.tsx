import { useState, useEffect } from 'react'
import { getModelConfigs, updateModelConfig } from '@/api/client'
import type { AIModelConfig } from '@/types/api'
import { ServerIcon, CloudIcon } from '@heroicons/react/24/outline'
import { Spinner } from '@/components/ui/Spinner'
import './ModelsPage.css'

export function ModelsPage() {
    const [configs, setConfigs] = useState<AIModelConfig[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [saving, setSaving] = useState<string | null>(null)
    const [savedType, setSavedType] = useState<string | null>(null)

    useEffect(() => {
        getModelConfigs()
            .then(data => { setConfigs(data); setError(null) })
            .catch(err => setError(err.message || 'Failed to fetch model configs'))
            .finally(() => setLoading(false))
    }, [])

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
        } catch (err: any) {
            setError(err.message || 'Failed to save configuration')
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
            <p className="models-page__loading-text">Loading model configurations…</p>
        </div>
    )

    return (
        <div className="models-page">
            <h1 className="models-page__title">AI Models</h1>
            <p className="models-page__desc">
                Configure which models run each task.
                Local models are downloaded automatically on first use.
            </p>

            {error && <div className="models-page__error">{error}</div>}

            {savedType && (
                <div className="model-modal-overlay" onClick={() => setSavedType(null)}>
                    <div className="model-modal" onClick={e => e.stopPropagation()}>
                        <div className="model-modal__icon">⚠️</div>
                        <p className="model-modal__title">Configuration saved — action required</p>
                        <div className="model-modal__body">
                            <div className="model-modal__row">
                                <span className="model-modal__row-icon">🔄</span>
                                <span>Restart the application for the new <strong>{savedType}</strong> model to take effect.</span>
                            </div>
                            {savedType === 'embedding' && (
                                <div className="model-modal__row">
                                    <span className="model-modal__row-icon">🗂️</span>
                                    <span>The embedding model changed — all photos need to be re-indexed. Run the pipeline again on your photo folders to rebuild the search index.</span>
                                </div>
                            )}
                        </div>
                        <div className="model-modal__footer">
                            <button className="model-modal__ok-btn" onClick={() => setSavedType(null)}>
                                Got it
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
                                {config.type}
                            </h2>
                            <span className={`model-card__badge model-card__badge--${config.mode}`}>
                                {config.mode}
                            </span>
                        </div>

                        <div className="model-card__form">
                            <div className="model-field">
                                <label className="model-field__label">Processing mode</label>
                                <select
                                    className="model-field__select"
                                    value={config.mode}
                                    onChange={e => handleChange(config.type, 'mode', e.target.value)}
                                >
                                    <option value="local">Local (GPU / CPU)</option>
                                    <option value="remote">Remote (API)</option>
                                </select>
                            </div>

                            <div className="model-field">
                                <label className="model-field__label">Model name / HuggingFace ID</label>
                                <input
                                    className="model-field__input"
                                    value={config.model_name}
                                    onChange={e => handleChange(config.type, 'model_name', e.target.value)}
                                    placeholder={config.mode === 'local'
                                        ? 'e.g. Qwen/Qwen2-VL-2B-Instruct'
                                        : config.type === 'vision' || config.type === 'clip' || config.type === 'ocr'
                                            ? 'e.g. gpt-4o  /  claude-3-haiku-20240307  /  llava'
                                            : config.type === 'translator'
                                                ? 'e.g. gpt-4o-mini  (not needed for deepl/libretranslate)'
                                                : 'e.g. gpt-4o-mini'
                                    }
                                />
                            </div>

                            {config.mode === 'remote' && (
                                <div className="model-card__remote">
                                    <div className="model-field">
                                        <label className="model-field__label">Provider</label>
                                        <select
                                            className="model-field__select"
                                            value={config.model_provider || ''}
                                            onChange={e => handleChange(config.type, 'model_provider', e.target.value)}
                                        >
                                            <option value="">— auto-detect —</option>
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
                                            <p className="model-field__hint">
                                                Set API base URL to your Ollama server (default: http://localhost:11434). No API key needed.
                                            </p>
                                        )}
                                        {config.model_provider === 'google_vertexai' && (
                                            <p className="model-field__hint">
                                                Requires GCP credentials (GOOGLE_APPLICATION_CREDENTIALS). No API key field needed.
                                            </p>
                                        )}
                                        {config.type === 'clip' && config.mode === 'remote' && (
                                            <p className="model-field__hint">
                                                Remote CLIP uses a vision LLM to classify tags from your vocabulary. Use the same vision model you configured above, or a dedicated one (e.g. gpt-4o-mini for cost savings).
                                            </p>
                                        )}
                                        {config.model_provider === 'deepl' && (
                                            <p className="model-field__hint">
                                                Enter your DeepL API key below. Model name is not used. Free tier: api-free.deepl.com (set in base URL).
                                            </p>
                                        )}
                                        {config.model_provider === 'libretranslate' && (
                                            <p className="model-field__hint">
                                                Self-hosted LibreTranslate. Set the base URL to your server. Model name is not used.
                                            </p>
                                        )}
                                    </div>
                                    <div className="model-field">
                                        <label className="model-field__label">
                                            {config.model_provider === 'ollama' ? 'Ollama server URL' : 'API base URL (optional)'}
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
                                            <label className="model-field__label">API key</label>
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
                                <label className="model-field__label">Similarity threshold</label>
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
                                    L2 distance cutoff — lower is stricter. Leave blank to auto-scale from the base threshold.
                                    Recommended: nomic&nbsp;768d&nbsp;→&nbsp;0.75, OpenAI&nbsp;text-embedding-3-small&nbsp;→&nbsp;1.05, OpenAI&nbsp;text-embedding-3-large&nbsp;→&nbsp;1.50.
                                </p>
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
                                        Saving…
                                    </>
                                ) : 'Save'}
                            </button>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    )
}
