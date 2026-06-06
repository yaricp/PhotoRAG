import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { getSettings, updateSetting } from '@/api/client'
import { getBaseUrl } from '@/api/base'
import './SettingsPage.css'

const isElectron = typeof window !== 'undefined' && !!window.electronAPI?.uninstall

const LANGUAGE_CODES = ['en', 'ru', 'es'] as const

export function SettingsPage() {
    const { t, i18n } = useTranslation()
    const navigate = useNavigate()
    const [defaultFolder, setDefaultFolder] = useState('')
    const [language, setLanguage] = useState('en')
    const [saving, setSaving] = useState(false)
    const [saved, setSaved] = useState(false)
    const [saveError, setSaveError] = useState<string | null>(null)
    const [uninstalling, setUninstalling] = useState(false)
    const [retranslating, setRetranslating] = useState(false)

    // Load settings once on mount. Dependency array is intentionally [] — re-reading
    // from DB every time i18n changes creates a feedback loop that reverts the language.
    useEffect(() => {
        let cancelled = false
        getSettings().then(async s => {
            if (cancelled) return
            const savedLanguage = s['default_language'] ?? 'en'
            setDefaultFolder(s['default_folder'] ?? '')
            setLanguage(savedLanguage)
            await i18n.changeLanguage(savedLanguage)
        }).catch(() => {
            if (cancelled) return
            const stored = localStorage.getItem('settings')
            if (stored) {
                const s = JSON.parse(stored)
                const savedLanguage = s.default_language ?? 'en'
                setDefaultFolder(s.default_folder ?? '')
                setLanguage(savedLanguage)
                i18n.changeLanguage(savedLanguage)
            }
        })
        return () => { cancelled = true }
    }, []) // eslint-disable-line react-hooks/exhaustive-deps

    async function handleSave() {
        setSaving(true)
        setSaved(false)
        setSaveError(null)
        const prevLang = i18n.language
        // Apply language change immediately so titles update even if DB save fails.
        if (language !== prevLang) {
            await i18n.changeLanguage(language)
        }
        try {
            await updateSetting('default_folder', defaultFolder)
            await updateSetting('default_language', language)
            if (language !== prevLang && language !== 'en') {
                setRetranslating(true)
                const base = await getBaseUrl()
                await fetch(`${base}/api/translation/retranslate-all`, { method: 'POST' })
                setRetranslating(false)
            }
            setSaved(true)
            setTimeout(() => setSaved(false), 2500)
        } catch (err) {
            setSaveError(err instanceof Error ? err.message : String(err))
            setRetranslating(false)
        } finally {
            setSaving(false)
        }
    }

    async function handleUninstall() {
        if (!window.electronAPI?.uninstall) return
        setUninstalling(true)
        try {
            await window.electronAPI.uninstall()
        } finally {
            setUninstalling(false)
        }
    }

    return (
        <div className="settings-page" data-testid="page-settings">
            <div className="settings-section">
                <p className="settings-section__heading">{t('settings.general')}</p>

                <div className="settings-row">
                    <label className="settings-row__label" htmlFor="default-language">
                        {t('settings.defaultLanguage')}
                    </label>
                    <select
                        id="default-language"
                        className="settings-select"
                        value={language}
                        onChange={e => setLanguage(e.target.value)}
                    >
                        {LANGUAGE_CODES.map(code => (
                            <option key={code} value={code}>{t(`languages.${code}`)}</option>
                        ))}
                    </select>
                </div>

                <div className="settings-row">
                    <label className="settings-row__label" htmlFor="default-folder">
                        {t('settings.defaultFolder')}
                    </label>
                    <input
                        id="default-folder"
                        type="text"
                        className="settings-input"
                        value={defaultFolder}
                        onChange={e => setDefaultFolder(e.target.value)}
                        placeholder="/Users/you/Photos"
                    />
                    <span className="settings-row__hint">{t('settings.defaultFolderHint')}</span>
                </div>
            </div>

            <div className="settings-footer">
                <button
                    className="settings-save-btn"
                    onClick={handleSave}
                    disabled={saving || retranslating}
                >
                    {retranslating ? t('settings.retranslating') : saving ? t('settings.saving') : t('settings.save')}
                </button>
                {saved && <span className="settings-saved">{t('settings.saved')}</span>}
                {saveError && <span className="settings-save-error">{saveError}</span>}
            </div>

            <div className="settings-section">
                <p className="settings-section__heading">{t('settings.clipVocabulary')}</p>
                <div className="settings-nav-cards">
                    <button className="settings-nav-card" onClick={() => navigate('/template-tags')}>
                        <span className="settings-nav-card__title">{t('settings.templateTags')}</span>
                        <span className="settings-nav-card__desc">{t('settings.templateTagsDesc')}</span>
                    </button>
                    <button className="settings-nav-card" onClick={() => navigate('/template-categories')}>
                        <span className="settings-nav-card__title">{t('settings.templateCategories')}</span>
                        <span className="settings-nav-card__desc">{t('settings.templateCategoriesDesc')}</span>
                    </button>
                </div>
            </div>

            {isElectron && (
                <div className="settings-section settings-section--danger">
                    <p className="settings-section__heading">{t('settings.dangerZone')}</p>
                    <div className="settings-danger-row">
                        <div className="settings-danger-info">
                            <span className="settings-danger-title">{t('settings.uninstall')}</span>
                            <span className="settings-danger-desc">{t('settings.uninstallDesc')}</span>
                        </div>
                        <button
                            className="settings-uninstall-btn"
                            onClick={handleUninstall}
                            disabled={uninstalling}
                        >
                            {uninstalling ? t('settings.uninstalling') : t('settings.uninstall')}
                        </button>
                    </div>
                </div>
            )}
        </div>
    )
}
