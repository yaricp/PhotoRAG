import React, { useEffect, useState } from 'react'

interface Props {
    onDone: () => void
}

export function StepInitDb({ onDone }: Props) {
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        window.electronAPI.initDb()
            .then(() => onDone())
            .catch((e: unknown) => setError(String(e)))
    }, [onDone])

    return (
        <div className="wizard-step">
            <h2>Initialising Database</h2>
            {!error && (
                <>
                    <div className="wizard-spinner" aria-label="Loading" />
                    <p>Setting up the photo library database…</p>
                </>
            )}
            {error && (
                <div className="wizard-error">
                    <p>Database initialisation failed: {error}</p>
                    <button
                        className="wizard-btn wizard-btn--primary"
                        onClick={() => { setError(null) }}
                    >
                        Retry
                    </button>
                </div>
            )}
        </div>
    )
}
