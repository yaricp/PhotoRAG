import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { ServerIcon, CloudIcon } from '@heroicons/react/24/outline'
import { PrivacyWarning } from '@/components/ui/PrivacyWarning'
import { applyWindowsRemoteModelDefaults, isWindowsAppPlatform } from '@/utils/windowsModelDefaults'
import { changeProcessingMode, changeProvider, getModelSuggestions, getProviderOptions, isLocalOllamaUrl, providerRequiresApiKey } from '@/utils/modelProviderOptions'
import { OllamaHelpDialog } from '@/components/ui/OllamaHelpDialog'

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

interface Props {
    onDone: (configs: ModelConfig[]) => void
}

export function StepModelConfig({ onDone }: Props) {
    const { t } = useTranslation()
    const isWindowsSetup = isWindowsAppPlatform()
    const [configs, setConfigs] = useState<ModelConfig[]>([])
    const [loading, setLoading] = useState(true)
    const [saving, setSaving] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [helpOpen, setHelpOpen] = useState(false)

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
                const sortedConfigs = sorted as ModelConfig[]
                const nextConfigs = isWindowsSetup
                    ? applyWindowsRemoteModelDefaults(sortedConfigs)
                    : sortedConfigs
                setConfigs(nextConfigs)
                setLoading(false)
            })
            .catch(e => { setError(String(e)); setLoading(false) })
    }, [isWindowsSetup])

    const handleChange = (type: string, field: keyof ModelConfig, value: string) => {
        setConfigs(prev => prev.map(c => {
            if (c.type !== type) return c
            if (field === 'mode') return changeProcessingMode(c, value)
            if (field === 'model_provider') return changeProvider(c, value)
            if (field === 'similarity_limit') {
                const num = parseFloat(value)
                return { ...c, similarity_limit: isNaN(num) ? undefined : num }
            }
            return { ...c, [field]: value }
        }))
    }

    const handleContinue = async () => {
        if (configs.some(c => c.mode === 'remote' && c.model_provider === 'ollama' && !c.model_name.trim())) {
            setError(t('wizard.stepModelConfig.ollamaModelRequired'))
            return
        }
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

            {isWindowsSetup && (
                <p className="wizard-notice wizard-notice--info">
                    {t('wizard.stepModelConfig.windowsRemoteOnlyNotice')}
                </p>
            )}

            {error && <div className="models-page__error">{error}</div>}

            <div className="wizard-model-config-layout">
            <div className="wizard-model-config-list">
                {configs.map(config => (
                    <div key={config.id} className="model-card">
                        <div className="model-card__header">
                            <h2 className="model-card__title">
                                {config.mode === 'local' || config.model_provider === 'ollama'
                                    ? <ServerIcon className="model-card__icon model-card__icon--local" />
                                    : <CloudIcon  className="model-card__icon model-card__icon--remote" />
                                }
                                {MODEL_LABELS[config.type] ?? config.type}
                            </h2>
                            <span className={`model-card__badge model-card__badge--${config.mode === 'local' || config.model_provider === 'ollama' ? 'local' : 'remote'}`}>
                                {config.mode === 'local' ? t('wizard.stepModelConfig.localMode')
                                    : config.model_provider === 'ollama' ? t('wizard.stepModelConfig.ollamaMode')
                                    : t('wizard.stepModelConfig.remoteMode')}
                            </span>
                        </div>

                        <div className="model-card__form">
                            <div className="model-field">
                                <label className="model-field__label">{t('wizard.stepModelConfig.processingMode')}</label>
                                <select
                                    className="model-field__select"
                                    value={config.mode === 'remote' && config.model_provider === 'ollama' ? 'ollama' : config.mode}
                                    onChange={e => handleChange(config.type, 'mode', e.target.value)}
                                >
                                    {!isWindowsSetup && (
                                        <option value="local">{t('wizard.stepModelConfig.localMode')}</option>
                                    )}
                                    <option value="remote">{t('wizard.stepModelConfig.remoteMode')}</option>
                                    <option value="ollama">{t('wizard.stepModelConfig.ollamaMode')}</option>
                                </select>
                            </div>

                            {config.mode === 'remote' && (
                                <div className="model-field">
                                    <label className="model-field__label">{t('wizard.stepModelConfig.provider')}</label>
                                    <select
                                        className="model-field__select"
                                        value={config.model_provider || ''}
                                        onChange={e => handleChange(config.type, 'model_provider', e.target.value)}
                                    >
                                        <option value="">{t('wizard.stepModelConfig.autoDetect')}</option>
                                        {getProviderOptions(config.type).map(provider => (
                                            <option key={provider.value} value={provider.value}>{provider.label}</option>
                                        ))}
                                    </select>
                                    {config.model_provider === 'ollama' && (
                                        <p className="model-field__hint">
                                            {t(isLocalOllamaUrl(config.url) ? 'wizard.stepModelConfig.ollamaHint' : 'wizard.stepModelConfig.ollamaRemoteHint')}{' '}
                                            <button type="button" className="help-article__link help-article__link-button" onClick={() => setHelpOpen(true)}>
                                                {t('wizard.stepModelConfig.ollamaHelpLink')}
                                            </button>
                                        </p>
                                    )}
                                    {config.type === 'clip' && (
                                        <p className="model-field__hint">
                                            {t('wizard.stepModelConfig.remoteClipHint')}
                                        </p>
                                    )}
                                    {config.model_provider === 'deepl' && (
                                        <p className="model-field__hint">{t('wizard.stepModelConfig.deepLHint')}</p>
                                    )}
                                </div>
                            )}

                            <div className="model-field">
                                <label className="model-field__label">{t('wizard.stepModelConfig.modelName')}</label>
                                <input
                                    className="model-field__input"
                                    value={config.model_name}
                                    onChange={e => handleChange(config.type, 'model_name', e.target.value)}
                                    placeholder={config.mode === 'local'
                                        ? t('wizard.stepModelConfig.localPlaceholder')
                                        : config.model_provider === 'ollama'
                                            ? getModelSuggestions('ollama', config.type)[0] ?? ''
                                        : t('wizard.stepModelConfig.remotePlaceholder')
                                    }
                                />
                                {config.mode === 'remote' && config.model_provider && (() => {
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
                                })()}
                            </div>

                            {config.mode === 'remote' && (
                                <div className="model-card__remote">
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

                                    {providerRequiresApiKey(config.model_provider) && (
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
            {helpOpen && <OllamaHelpDialog onClose={() => setHelpOpen(false)} />}
        </div>
    )
}
