import { useState, useEffect } from 'react'
import { getModelConfigs, updateModelConfig } from '@/api/client'
import type { AIModelConfig } from '@/types/api'
import { ServerIcon, CloudIcon } from '@heroicons/react/24/outline'
import './ModelsPage.css'

export function ModelsPage() {
    const [configs, setConfigs] = useState<AIModelConfig[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [saving, setSaving] = useState<string | null>(null)

    const fetchConfigs = async () => {
        try {
            const data = await getModelConfigs()
            setConfigs(data)
            setError(null)
        } catch (err: any) {
            setError(err.message || 'Failed to fetch models configurations')
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchConfigs()
    }, [])

    const handleSave = async (config: AIModelConfig) => {
        setSaving(config.type)
        try {
            const updated = await updateModelConfig(config.type, {
                mode: config.mode,
                model_name: config.model_name,
                url: config.url || undefined,
                api_key: config.api_key || undefined
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

    if (loading) return <div className="loading-container">
        <div className="loading-text">Loading AI models configuration...</div>
    </div>

    return (
        <div className="models-page-container">
            <div className="models-page-header">
                <div className="models-page-header-icon-wrapper">
                    <ServerIcon className="models-page-header-icon w-6 h-6 shrink-0 text-blue-400" style={{ width: '1.5rem', height: '1.5rem' }} />
                </div>
                <h1 className="models-page-title">AI Models Configuration</h1>
            </div>
            
            <p className="models-page-description">
                Configure your AI models here. Changes take effect immediately without restarting the server.
                Local models will be downloaded automatically when used for the first time.
            </p>

            {error && (
                <div className="models-page-error">
                    {error}
                </div>
            )}

            <div className="models-grid">
                {configs.map(config => (
                    <div key={config.id} className="model-card">
                        <div className="model-card-header">
                            <h2 className="model-card-title">
                                {config.mode === 'local' ? (
                                    <ServerIcon className="model-card-icon model-card-icon--local w-5 h-5 shrink-0 text-blue-400" style={{ width: '1.25rem', height: '1.25rem' }} />
                                ) : (
                                    <CloudIcon className="model-card-icon model-card-icon--remote w-5 h-5 shrink-0 text-purple-400" style={{ width: '1.25rem', height: '1.25rem' }} />
                                )}
                                {config.type}
                            </h2>
                            <span className={`model-card-badge ${
                                config.mode === 'local' ? 'model-card-badge--local' : 'model-card-badge--remote'
                            }`}>
                                {config.mode}
                            </span>
                        </div>

                        <div className="model-card-form">
                            <div className="form-group">
                                <label className="form-label">Processing Mode</label>
                                <select 
                                    className="form-input"
                                    value={config.mode}
                                    onChange={(e) => handleChange(config.type, 'mode', e.target.value as 'local'|'remote')}
                                >
                                    <option value="local">Local execution (GPU/CPU)</option>
                                    <option value="remote">Remote execution (API)</option>
                                </select>
                            </div>

                            <div className="form-group">
                                <label className="form-label">Model Name / HuggingFace ID</label>
                                <input 
                                    className="form-input"
                                    value={config.model_name}
                                    onChange={(e) => handleChange(config.type, 'model_name', e.target.value)}
                                    placeholder={config.mode === 'local' ? "e.g. Qwen/Qwen2-VL-2B-Instruct" : "e.g. gpt-4o-mini"}
                                />
                            </div>

                            {config.mode === 'remote' && (
                                <div className="remote-config-container">
                                    <div className="form-group">
                                        <label className="form-label form-label--remote">API Base URL (Optional)</label>
                                        <input 
                                            className="form-input form-input--remote"
                                            value={config.url || ''}
                                            onChange={(e) => handleChange(config.type, 'url', e.target.value)}
                                            placeholder="https://api.openai.com/v1"
                                        />
                                    </div>
                                    <div className="form-group">
                                        <label className="form-label form-label--remote">API Key</label>
                                        <input 
                                            className="form-input form-input--remote"
                                            type="password"
                                            value={config.api_key || ''}
                                            onChange={(e) => handleChange(config.type, 'api_key', e.target.value)}
                                            placeholder="sk-..."
                                        />
                                    </div>
                                </div>
                            )}
                        </div>
                        
                        <div className="model-card-footer">
                            <button
                                onClick={() => handleSave(config)}
                                disabled={saving === config.type}
                                className="btn-save"
                            >
                                {saving === config.type ? (
                                    <>
                                        <svg className="loading-spinner" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                        </svg>
                                        Saving...
                                    </>
                                ) : 'Save Configuration'}
                            </button>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    )
}