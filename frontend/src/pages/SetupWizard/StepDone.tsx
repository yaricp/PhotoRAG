import React, { useState } from 'react'
import { useTranslation } from 'react-i18next'

interface Props {
    skippedModels?: string[]
    onComplete: () => void
}

export function StepDone({ skippedModels, onComplete }: Props) {
    const { t } = useTranslation()
    const [launching, setLaunching] = useState(false)

    const handleLaunch = async () => {
        setLaunching(true)
        await window.electronAPI.completeSetup(
            skippedModels && skippedModels.length > 0
                ? { skippedModels }
                : undefined
        )
        onComplete()
    }

    return (
        <div className="wizard-step">
            <div className="wizard-icon">✅</div>
            <h2>{t('wizard.stepDone.title')}</h2>
            <p>{t('wizard.stepDone.subtitle')}</p>
            <div className="wizard-actions">
                <button
                    className="wizard-btn wizard-btn--primary"
                    onClick={handleLaunch}
                    disabled={launching}
                >
                    {launching ? t('wizard.stepDone.launching') : t('wizard.stepDone.launchButton')}
                </button>
            </div>
        </div>
    )
}
