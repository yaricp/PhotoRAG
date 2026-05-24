import React, { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

interface Props {
    onDone: () => void
}

export function StepInitDb({ onDone }: Props) {
    const { t } = useTranslation()
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        window.electronAPI.initDb()
            .then(() => onDone())
            .catch((e: unknown) => setError(String(e)))
    }, [onDone])

    return (
        <div className="wizard-step">
            <h2>{t('wizard.stepInitDb.title')}</h2>
            {!error && (
                <>
                    <div className="wizard-spinner" aria-label="Loading" />
                    <p>{t('wizard.stepInitDb.initializing')}</p>
                </>
            )}
            {error && (
                <div className="wizard-error">
                    <p>{t('wizard.stepInitDb.errorMessage', { error })}</p>
                    <button
                        className="wizard-btn wizard-btn--primary"
                        onClick={() => { setError(null) }}
                    >
                        {t('wizard.stepInitDb.retryButton')}
                    </button>
                </div>
            )}
        </div>
    )
}
