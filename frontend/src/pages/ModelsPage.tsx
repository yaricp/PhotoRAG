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
            })
            setConfigs(prev => prev.map(c => c.type === updated.type ? updated : c))
        } catch (err: any) {
            setError(err.message || 'Failed to save configuration')
        } finally {
            setSaving(null)
        }
    }

    const handleChange = (type: string, field: keyof AIModelConfig, value: string) => {
        setConfigs(prev => prev.map(c => c.type === type ? { ...c, [field]: value } : c))
    }

    if (loading) return <div className="models-page"><Spinner size="lg" /></div>

    return (
        <div className="models-page">
            <h1 className="models-page__title">AI Models</h1>
            <p className="models-page__desc">
                Configure which models run each task. Changes apply immediately — no server restart needed.
                Local models are downloaded automatically on first use.
            </p>

            {error && <div className="models-page__error">{error}</div>}

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
                                    placeholder={config.mode === 'local' ? 'e.g. Qwen/Qwen2-VL-2B-Instruct' : 'e.g. gpt-4o-mini'}
                                />
                            </div>

                            {config.mode === 'remote' && (
                                <div className="model-card__remote">
                                    <div className="model-field">
                                        <label className="model-field__label">API base URL (optional)</label>
                                        <input
                                            className="model-field__input"
                                            value={config.url || ''}
                                            onChange={e => handleChange(config.type, 'url', e.target.value)}
                                            placeholder="https://api.openai.com/v1"
                                        />
                                    </div>
                                    <div className="model-field">
                                        <label className="model-field__label">API key</label>
                                        <input
                                            className="model-field__input"
                                            type="password"
                                            value={config.api_key || ''}
                                            onChange={e => handleChange(config.type, 'api_key', e.target.value)}
                                            placeholder="sk-..."
                                        />
                                    </div>
                                </div>
                            )}
                        </div>

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
