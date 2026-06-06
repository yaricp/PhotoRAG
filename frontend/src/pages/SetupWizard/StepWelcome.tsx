import React from 'react'
import { useTranslation } from 'react-i18next'

interface Props {
    onContinue: () => void
}

export function StepWelcome({ onContinue }: Props) {
    const { t } = useTranslation()
    return (
        <div className="wizard-step">
            <div className="wizard-icon">📷</div>
            <h1>{t('wizard.welcome.title')}</h1>
            <p className="wizard-subtitle">{t('wizard.welcome.subtitle')}</p>
            <ul className="wizard-checklist">
                <li>{t('wizard.welcome.installDeps')}</li>
                <li>{t('wizard.welcome.initDb')}</li>
                <li>{t('wizard.welcome.downloadModels')}</li>
            </ul>
            <div className="wizard-actions">
                <button className="wizard-btn wizard-btn--primary" onClick={onContinue}>
                    {t('wizard.welcome.getStarted')}
                </button>
            </div>
        </div>
    )
}
