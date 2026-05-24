import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import './PrivacyWarning.css'

export function PrivacyWarning() {
    const { t } = useTranslation()
    const [open, setOpen] = useState(false)

    return (
        <div className="privacy-warning">
            <div className="privacy-warning__compact">
                <span className="privacy-warning__title">{t('privacy.shortTitle')}</span>
                <p className="privacy-warning__short">{t('privacy.shortText')}</p>
                <button
                    className="privacy-warning__expand-btn"
                    onClick={() => setOpen(true)}
                >
                    {t('privacy.expandButton')}
                </button>
            </div>

            {open && (
                <div
                    role="dialog"
                    aria-modal="true"
                    aria-label={t('privacy.fullTitle')}
                    className="privacy-warning__backdrop"
                    onClick={() => setOpen(false)}
                >
                    <div
                        className="privacy-warning__modal"
                        onClick={e => e.stopPropagation()}
                    >
                        <div className="privacy-warning__modal-header">
                            <h2 className="privacy-warning__modal-title">{t('privacy.fullTitle')}</h2>
                            <button
                                className="privacy-warning__close-btn"
                                onClick={() => setOpen(false)}
                                aria-label="Dismiss"
                            >
                                ✕
                            </button>
                        </div>
                        <div className="privacy-warning__modal-body">
                            {t('privacy.fullText').split('\n').map((line, i) => (
                                line.trim() === ''
                                    ? <br key={i} />
                                    : <p key={i}>{line}</p>
                            ))}
                        </div>
                        <div className="privacy-warning__modal-footer">
                            <button
                                className="privacy-warning__close-btn--primary"
                                onClick={() => setOpen(false)}
                            >
                                {t('privacy.closeButton')}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
