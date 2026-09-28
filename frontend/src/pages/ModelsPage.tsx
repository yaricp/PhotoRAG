import { useState, useEffect, useRef, useCallback, useSyncExternalStore } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { getModelConfigs, updateModelConfig, getSystemStatus } from '@/api/client'
import type { AIModelConfig } from '@/types/api'
import { ServerIcon, CloudIcon } from '@heroicons/react/24/outline'
import { Spinner } from '@/components/ui/Spinner'
import { PrivacyWarning } from '@/components/ui/PrivacyWarning'
import { applyWindowsRemoteModelDefaults, isWindowsAppPlatform } from '@/utils/windowsModelDefaults'
import { changeProcessingMode, changeProvider, getModelSuggestions, getProviderOptions, isLocalOllamaUrl, providerRequiresApiKey } from '@/utils/modelProviderOptions'
import { ensureOllamaModel, getOllamaDownloadStates, ollamaDownloadKey, subscribeOllamaDownloads } from '@/utils/ollamaDownloads'
import { OllamaHelpDialog } from '@/components/ui/OllamaHelpDialog'
import './ModelsPage.css'

type ModelStatusMap = Record<string, string>  // model type → status

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
    const [saving, setSaving] = useState<Set<string>>(new Set())
    const [savedType, setSavedType] = useState<string | null>(null)
    const [helpOpen, setHelpOpen] = useState(false)
    const [pendingOllama, setPendingOllama] = useState<Record<string, string>>({})
    const [ollamaErrors, setOllamaErrors] = useState<Record<string, string>>({})
    const [ollamaSaved, setOllamaSaved] = useState<Set<string>>(new Set())
    const pendingTypes = useRef(new Set<string>())
    const ollamaDownloads = useSyncExternalStore(subscribeOllamaDownloads, getOllamaDownloadStates)
    const [modelStatuses, setModelStatuses] = useState<ModelStatusMap>({})
    const isWindowsApp = isWindowsAppPlatform()
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
            .then(data => {
                setConfigs(isWindowsApp ? applyWindowsRemoteModelDefaults(data) : data)
                setError(null)
            })
            .catch(err => setError(err.message || t('models.error')))
            .finally(() => setLoading(false))
        startPolling()
        return () => { if (pollRef.current) clearInterval(pollRef.current) }
    }, [startPolling, isWindowsApp])

    const persistConfig = async (config: AIModelConfig, showModal = true) => {
        setSaving(prev => new Set(prev).add(config.type))
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
            if (showModal) setSavedType(config.type)
            if (config.mode === 'local') startPolling()
        } catch (err: any) {
            if (showModal) setError(err.message || t('models.errorSaving'))
            throw err
        } finally {
            setSaving(prev => {
                const next = new Set(prev)
                next.delete(config.type)
                return next
            })
        }
    }

    const handleSave = (config: AIModelConfig) => {
        if (pendingTypes.current.has(config.type)) return
        if (config.mode === 'remote' && config.model_provider === 'ollama') {
            if (!config.model_name.trim()) {
                setError(t('wizard.stepModelConfig.ollamaModelRequired'))
                return
            }
            if (!isLocalOllamaUrl(config.url)) {
                void persistConfig(config).catch(() => {})
                return
            }
            const key = ollamaDownloadKey(config.model_name, config.url)
            pendingTypes.current.add(config.type)
            setPendingOllama(prev => ({ ...prev, [config.type]: key }))
            setOllamaErrors(prev => ({ ...prev, [config.type]: '' }))
            setOllamaSaved(prev => {
                const next = new Set(prev)
                next.delete(config.type)
                return next
            })
            void (async () => {
                try {
                    await ensureOllamaModel(config.model_name, config.url)
                    await persistConfig(config, false)
                    setOllamaSaved(prev => new Set(prev).add(config.type))
                } catch (cause) {
                    setOllamaErrors(prev => ({ ...prev, [config.type]: String(cause) }))
                } finally {
                    pendingTypes.current.delete(config.type)
                    setPendingOllama(prev => {
                        const next = { ...prev }
                        delete next[config.type]
                        return next
                    })
                }
            })()
            return
        }
        void persistConfig(config).catch(() => {})
    }

    const handleChange = (type: string, field: keyof AIModelConfig, value: string) => {
        setOllamaSaved(prev => {
            const next = new Set(prev)
            next.delete(type)
            return next
        })
        setOllamaErrors(prev => ({ ...prev, [type]: '' }))
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

    if (loading) return (
        <div className="models-page models-page--loading">
            <Spinner size="lg" />
            <p className="models-page__loading-text">{t('models.loading')}</p>
        </div>
    )

    return (
        <div className="models-page">
            <p className="models-page__desc">{t('models.desc')}</p>
            <p><Link to="/ollama-models" className="help-article__link">{t('sidebar.ollamaModels')}</Link></p>

            {isWindowsApp && (
                <div className="models-page__notice">
                    {t('models.windowsRemoteOnlyNotice')}
                </div>
            )}

            {error && <div className="models-page__error">{error}</div>}

            {helpOpen && <OllamaHelpDialog onClose={() => setHelpOpen(false)} />}

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
                                        : configs.find(c => c.type === savedType)?.model_provider === 'ollama'
                                            ? t('models.modelOllama') : t('models.modelRemote')}
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
                {configs.map(config => {
                    const pendingKey = pendingOllama[config.type]
                    const download = pendingKey ? ollamaDownloads[pendingKey] : undefined
                    const busy = Boolean(pendingKey) || saving.has(config.type)
                    const percent = download?.total
                        ? Math.min(99, Math.round(download.completed / download.total * 100))
                        : download?.phase === 'ready' ? 100 : 0
                    return <div key={config.id} className="model-card">
                        <div className="model-card__header">
                            <h2 className="model-card__title">
                                {config.mode === 'local' || config.model_provider === 'ollama'
                                    ? <ServerIcon className="model-card__icon model-card__icon--local" />
                                    : <CloudIcon  className="model-card__icon model-card__icon--remote" />
                                }
                                {t(MODEL_TYPE_LABEL_KEY[config.type] ?? '', { defaultValue: config.type })}
                            </h2>
                            <div className="model-card__badges">
                                <span className={`model-card__badge model-card__badge--${config.mode === 'local' || config.model_provider === 'ollama' ? 'local' : 'remote'}`}>
                                    {config.mode === 'local' ? t('models.local')
                                        : config.model_provider === 'ollama' ? t('wizard.stepModelConfig.ollamaMode')
                                        : t('models.remote')}
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
                                    disabled={busy}
                                    value={config.mode === 'remote' && config.model_provider === 'ollama' ? 'ollama' : config.mode}
                                    onChange={e => handleChange(config.type, 'mode', e.target.value)}
                                >
                                    {!isWindowsApp && (
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
                                        disabled={busy}
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
                            )}

                            <div className="model-field">
                                <label className="model-field__label">{t('wizard.stepModelConfig.modelName')}</label>
                                <input
                                    className="model-field__input"
                                    disabled={busy}
                                    value={config.model_name}
                                    onChange={e => handleChange(config.type, 'model_name', e.target.value)}
                                    placeholder={config.mode === 'local'
                                        ? t('wizard.stepModelConfig.localPlaceholder')
                                        : config.model_provider === 'ollama'
                                            ? getModelSuggestions('ollama', config.type)[0] ?? ''
                                        : config.type === 'vision' || config.type === 'clip' || config.type === 'ocr'
                                            ? 'e.g. gpt-4o  /  claude-3-haiku-20240307'
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
                                                        disabled={busy}
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
                                        <label className="model-field__label">
                                            {config.model_provider === 'ollama'
                                                ? t('wizard.stepModelConfig.ollamaUrl')
                                                : t('wizard.stepModelConfig.baseUrl')}
                                        </label>
                                        <input
                                            className="model-field__input"
                                            disabled={busy}
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
                                                disabled={busy}
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
                                    disabled={busy}
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

                        {pendingKey && <div className="model-card__download" role="status" aria-live="polite">
                            <span>{saving.has(config.type) ? t('models.saving')
                                : download?.phase === 'downloading' ? t('models.ollamaDownloading', { model: config.model_name.trim() })
                                    : t('models.ollamaChecking', { model: config.model_name.trim() })}</span>
                            {download?.status && <span>{download.status}</span>}
                            {download?.phase === 'downloading' && <div className="model-card__progress" role="progressbar"
                                aria-label={config.model_name.trim()} aria-valuemin={0} aria-valuemax={100}
                                aria-valuenow={download.total ? percent : undefined}>
                                <div className="model-card__progress-fill" style={{ width: download.total ? `${percent}%` : '100%' }} />
                            </div>}
                            {download?.phase === 'downloading' && download.total > 0 && <span>{percent}%</span>}
                        </div>}
                        {ollamaErrors[config.type] && <p className="model-card__download-error" role="alert">
                            {t('models.ollamaDownloadError', { error: ollamaErrors[config.type] })}
                        </p>}
                        {ollamaSaved.has(config.type) && !pendingKey && <p className="model-card__saved" role="status">{t('models.configSaved')}</p>}
                        <div className="model-card__footer">
                            <button
                                className="model-card__save-btn"
                                onClick={() => handleSave(config)}
                                disabled={busy}
                            >
                                {busy ? (
                                    <>
                                        <svg className="model-card__spinner" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                            <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" opacity="0.25" />
                                            <path fill="currentColor" opacity="0.75" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                        </svg>
                                    {saving.has(config.type) ? t('models.saving') : t('models.ollamaPreparing')}
                                    </>
                                ) : t('models.save')}
                            </button>
                        </div>
                    </div>
                })}
            </div>
                <PrivacyWarning />
            </div>
        </div>
    )
}
