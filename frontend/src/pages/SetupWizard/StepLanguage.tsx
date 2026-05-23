import React, { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { updateSetting } from '@/api/client'

const LANGUAGES = [
    { code: 'en', flag: '🇬🇧', native: 'English' },
    { code: 'ru', flag: '🇷🇺', native: 'Русский' },
    { code: 'es', flag: '🇪🇸', native: 'Español' },
]

interface Props {
    onContinue: () => void
}

export function StepLanguage({ onContinue }: Props) {
    const { t, i18n } = useTranslation()
    const [selected, setSelected] = useState(i18n.language ?? 'en')
    const [saving, setSaving] = useState(false)

    async function handleContinue() {
        setSaving(true)
        try {
            await i18n.changeLanguage(selected)
            await updateSetting('default_language', selected)
        } finally {
            setSaving(false)
        }
        onContinue()
    }

    return (
        <div className="wizard-step">
            <div className="wizard-icon">🌐</div>
            <h1>{t('wizard.language.title')}</h1>
            <p className="wizard-subtitle">{t('wizard.language.subtitle')}</p>

            <div className="wizard-lang-list">
                {LANGUAGES.map(lang => (
                    <button
                        key={lang.code}
                        className={`wizard-lang-option${selected === lang.code ? ' wizard-lang-option--selected' : ''}`}
                        onClick={() => setSelected(lang.code)}
                    >
                        <span className="wizard-lang-flag">{lang.flag}</span>
                        <span className="wizard-lang-name">{lang.native}</span>
                    </button>
                ))}
            </div>

            <div className="wizard-actions">
                <button
                    className="wizard-btn wizard-btn--primary"
                    onClick={handleContinue}
                    disabled={saving}
                >
                    {t('wizard.language.continue')}
                </button>
            </div>
        </div>
    )
}
