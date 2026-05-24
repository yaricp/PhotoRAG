import React, { useState } from 'react'

interface Props {
    text: string
}

export function OcrPanel({ text }: Props) {
    const [copied, setCopied] = useState(false)

    const handleCopy = async () => {
        await navigator.clipboard.writeText(text)
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
    }

    return (
        <div data-testid="ocr-panel" className="ocr-panel">
            <div className="ocr-panel__text">{text}</div>
            <button
                className="ocr-panel__copy-btn"
                onClick={handleCopy}
                aria-label={copied ? 'Copied' : 'Copy'}
            >
                {copied ? 'Copied' : 'Copy'}
            </button>
        </div>
    )
}
