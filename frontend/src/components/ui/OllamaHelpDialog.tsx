import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { useTranslation } from 'react-i18next'
import { HelpArticle } from '@/pages/HelpPage/HelpArticle'
import '@/pages/HelpPage/HelpPage.css'
import './OllamaHelpDialog.css'

export function OllamaHelpDialog({ onClose }: { onClose: () => void }) {
    const { t } = useTranslation()
    const closeRef = useRef<HTMLButtonElement>(null)

    useEffect(() => {
        closeRef.current?.focus()
        const onKeyDown = (event: KeyboardEvent) => {
            if (event.key === 'Escape') onClose()
        }
        window.addEventListener('keydown', onKeyDown)
        return () => window.removeEventListener('keydown', onKeyDown)
    }, [onClose])

    return createPortal(
        <div className="ollama-help-backdrop" onMouseDown={event => {
            if (event.target === event.currentTarget) onClose()
        }}>
            <section className="ollama-help-dialog" role="dialog" aria-modal="true" aria-label={t('help.topics.local-ollama.title')}>
                <button ref={closeRef} type="button" className="ollama-help-close" onClick={onClose}
                    aria-label={t('privacy.closeButton')}>×</button>
                <div className="ollama-help-content"><HelpArticle topic="local-ollama" /></div>
            </section>
        </div>, document.body
    )
}
