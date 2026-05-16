import React from 'react'

interface Props {
    onContinue: () => void
}

export function StepWelcome({ onContinue }: Props) {
    return (
        <div className="wizard-step">
            <div className="wizard-icon">📷</div>
            <h1>Welcome to PhotoRAG</h1>
            <p className="wizard-subtitle">
                Let's set up your AI-powered photo library. This will take a few minutes.
            </p>
            <ul className="wizard-checklist">
                <li>Install Python dependencies</li>
                <li>Initialise the database</li>
                <li>Download AI models of your choice</li>
            </ul>
            <div className="wizard-actions">
                <button className="wizard-btn wizard-btn--primary" onClick={onContinue}>
                    Get Started
                </button>
            </div>
        </div>
    )
}
