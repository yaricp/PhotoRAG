import React, { useState } from 'react'

export interface TesseractStatus {
    available: boolean
    ocr_mode: string
    path?: string | null
}

interface Props {
    status: TesseractStatus | null
}

const BREW_CMD = 'brew install tesseract'
const STORAGE_KEY = 'tesseract_banner_dismissed'

export function TesseractBanner({ status }: Props) {
    const [dismissed, setDismissed] = useState(
        () => localStorage.getItem(STORAGE_KEY) === '1'
    )
    const [copied, setCopied] = useState(false)

    if (!status || status.available || status.ocr_mode === 'remote' || dismissed) {
        return null
    }

    const handleCopy = () => {
        navigator.clipboard.writeText(BREW_CMD).then(() => {
            setCopied(true)
            setTimeout(() => setCopied(false), 2000)
        })
    }

    const handleDismiss = () => {
        localStorage.setItem(STORAGE_KEY, '1')
        setDismissed(true)
    }

    return (
        <div className="tesseract-banner" role="alert">
            <span className="tesseract-banner__icon">⚠️</span>
            <span className="tesseract-banner__text">
                Tesseract OCR is not installed. OCR features will not work locally.
                Install via Homebrew:{' '}
                <code className="tesseract-banner__cmd">{BREW_CMD}</code>
            </span>
            <button
                className="tesseract-banner__btn"
                onClick={handleCopy}
                aria-label="Copy"
            >
                {copied ? 'Copied!' : 'Copy'}
            </button>
            <button
                className="tesseract-banner__btn tesseract-banner__btn--dismiss"
                onClick={handleDismiss}
                aria-label="Dismiss"
            >
                ✕
            </button>
        </div>
    )
}
