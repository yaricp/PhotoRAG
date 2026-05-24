import React, { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

interface Props {
    onDone: () => void
}

export function StepInstallDeps({ onDone }: Props) {
    const { t } = useTranslation()
    const [installing, setInstalling] = useState(false)
    const [progress, setProgress] = useState(0)
    const [logLine, setLogLine] = useState('')
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        window.electronAPI.onInstallDepsProgress(({ percent, line }) => {
            setProgress(percent)
            setLogLine(line)
        })
    }, [])

    const handleInstall = async () => {
        setInstalling(true)
        setError(null)
        try {
            await window.electronAPI.installDeps()
            onDone()
        } catch (e) {
            setError(String(e))
            setInstalling(false)
        }
    }

    return (
        <div className="wizard-step">
            <h2>{t('wizard.stepInstallDeps.title')}</h2>
            <p>{t('wizard.stepInstallDeps.subtitle')}</p>

            {!installing && !error && (
                <div className="wizard-actions">
                    <button
                        className="wizard-btn wizard-btn--primary"
                        onClick={handleInstall}
                    >
                        {t('wizard.stepInstallDeps.installButton')}
                    </button>
                </div>
            )}

            {installing && (
                <div className="wizard-progress-wrap">
                    <div
                        role="progressbar"
                        aria-valuenow={progress}
                        aria-valuemin={0}
                        aria-valuemax={100}
                        className="wizard-progressbar"
                    >
                        <div className="wizard-progressbar__fill" style={{ width: `${progress}%` }} />
                    </div>
                    {logLine && <p className="wizard-log">{logLine}</p>}
                </div>
            )}

            {error && (
                <div className="wizard-error">
                    <p>{t('wizard.stepInstallDeps.errorMessage', { error })}</p>
                    <button
                        className="wizard-btn wizard-btn--primary"
                        onClick={handleInstall}
                    >
                        {t('wizard.stepInstallDeps.retryButton')}
                    </button>
                </div>
            )}
        </div>
    )
}
