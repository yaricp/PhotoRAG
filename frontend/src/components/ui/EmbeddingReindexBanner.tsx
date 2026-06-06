import React, { useState, useEffect } from 'react'
import { getReindexStatus } from '@/api/client'
import './PipelineWarningBanner.css'

export function EmbeddingReindexBanner() {
    const [status, setStatus] = useState<{ needed: boolean; total: number; indexed: number } | null>(null)
    const [dismissed, setDismissed] = useState(false)

    useEffect(() => {
        getReindexStatus()
            .then(setStatus)
            .catch(() => {})
    }, [])

    if (!status?.needed || dismissed) return null

    const missing = status.total - status.indexed

    return (
        <div className="pipeline-warning-banner" role="alert">
            <span className="pipeline-warning-banner__icon">⚠</span>
            <span className="pipeline-warning-banner__text">
                <strong>Embedding model changed — semantic search is incomplete.</strong>
                {' '}
                {missing} of {status.total} photo{status.total !== 1 ? 's' : ''} need
                {status.total === 1 ? 's' : ''} re-indexing.
                {' '}
                Run the pipeline on your photo folders to rebuild the search index.
            </span>
            <button
                className="pipeline-warning-banner__dismiss"
                onClick={() => setDismissed(true)}
                aria-label="Dismiss warning"
            >
                ✕
            </button>
        </div>
    )
}
