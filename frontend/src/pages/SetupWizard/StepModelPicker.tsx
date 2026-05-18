import React from 'react'
import { MODELS, formatSizeMB, totalSizeLabel } from './models'

interface Props {
    selected: Set<string>
    onChange: (next: Set<string>) => void
    onContinue: () => void
    // When provided, only models whose id is in this set are shown (local-mode ones).
    // Models not in this set are configured as remote and don't need downloading.
    localOnlyTypes?: Set<string>
}

export function StepModelPicker({ selected, onChange, onContinue, localOnlyTypes }: Props) {
    const visibleModels = localOnlyTypes
        ? MODELS.filter(m => localOnlyTypes.has(m.id))
        : MODELS

    const allOptionalIds = visibleModels.filter(m => !m.required).map(m => m.id)
    const allOptionalSkipped = allOptionalIds.every(id => !selected.has(id))

    const toggle = (id: string, checked: boolean) => {
        const next = new Set(selected)
        if (checked) next.add(id)
        else next.delete(id)
        onChange(next)
    }

    const handleSkipAll = (checked: boolean) => {
        const next = new Set(visibleModels.filter(m => m.required).map(m => m.id))
        if (!checked) {
            allOptionalIds.forEach(id => next.add(id))
        }
        onChange(next)
    }

    if (visibleModels.length === 0) {
        return (
            <div className="wizard-step">
                <h2>Download Models</h2>
                <p>All models are configured to use remote APIs — no local downloads needed.</p>
                <div className="wizard-actions">
                    <button className="wizard-btn wizard-btn--primary" onClick={onContinue}>
                        Continue
                    </button>
                </div>
            </div>
        )
    }

    return (
        <div className="wizard-step">
            <h2>Choose Models to Download</h2>
            <p>Required models are always installed. Optional models add extra features.</p>

            <div className="wizard-model-list">
                {visibleModels.map(model => (
                    <label key={model.id} className="wizard-model-row" htmlFor={`model-${model.id}`}>
                        <input
                            type="checkbox"
                            id={`model-${model.id}`}
                            aria-label={model.name}
                            checked={selected.has(model.id)}
                            disabled={model.required}
                            onChange={e => toggle(model.id, e.target.checked)}
                        />
                        <span className="wizard-model-info">
                            <span className="wizard-model-name">{model.name}</span>
                            <span className="wizard-model-desc">{model.desc}</span>
                        </span>
                        <span className="wizard-model-size">{formatSizeMB(model.sizeMB)}</span>
                    </label>
                ))}
            </div>

            {allOptionalIds.length > 0 && (
                <label className="wizard-skip-all" htmlFor="skip-all-optional">
                    <input
                        type="checkbox"
                        id="skip-all-optional"
                        aria-label="Skip all optional"
                        checked={allOptionalSkipped}
                        onChange={e => handleSkipAll(e.target.checked)}
                    />
                    Skip all optional models
                </label>
            )}

            <p className="wizard-total-size">
                Total download: <strong>{totalSizeLabel(selected)}</strong>
            </p>

            <div className="wizard-actions">
                <button className="wizard-btn wizard-btn--primary" onClick={onContinue}>
                    Continue
                </button>
            </div>
        </div>
    )
}
