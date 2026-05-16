import React, { useEffect, useState } from 'react'

interface Props {
    onDone: () => void
}

export function StepInstallDeps({ onDone }: Props) {
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
            <h2>Install Dependencies</h2>
            <p>We'll install the required Python packages into an isolated virtual environment.</p>

            {!installing && !error && (
                <div className="wizard-actions">
                    <button
                        className="wizard-btn wizard-btn--primary"
                        onClick={handleInstall}
                    >
                        Install
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
                    <p>Installation failed: {error}</p>
                    <button
                        className="wizard-btn wizard-btn--primary"
                        onClick={handleInstall}
                    >
                        Retry
                    </button>
                </div>
            )}
        </div>
    )
}
