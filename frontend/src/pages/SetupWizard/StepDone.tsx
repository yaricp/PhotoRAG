import React, { useState } from 'react'

interface Props {
    onComplete: () => void
}

export function StepDone({ onComplete }: Props) {
    const [launching, setLaunching] = useState(false)

    const handleLaunch = async () => {
        setLaunching(true)
        await window.electronAPI.completeSetup()
        onComplete()
    }

    return (
        <div className="wizard-step">
            <div className="wizard-icon">✅</div>
            <h2>Setup Complete!</h2>
            <p>PhotoRAG is ready. Click Launch to open your photo library.</p>
            <div className="wizard-actions">
                <button
                    className="wizard-btn wizard-btn--primary"
                    onClick={handleLaunch}
                    disabled={launching}
                >
                    {launching ? 'Launching…' : 'Launch'}
                </button>
            </div>
        </div>
    )
}
