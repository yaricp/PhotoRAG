import React, { useState } from 'react'
import { StepWelcome } from './StepWelcome'
import { StepInstallDeps } from './StepInstallDeps'
import { StepInitDb } from './StepInitDb'
import { StepModelPicker } from './StepModelPicker'
import { StepDownloading } from './StepDownloading'
import { StepDone } from './StepDone'
import { MODELS } from './models'
import './SetupWizard.css'

type Step = 'welcome' | 'install-deps' | 'init-db' | 'model-picker' | 'downloading' | 'done'

const STEP_ORDER: Step[] = ['welcome', 'install-deps', 'init-db', 'model-picker', 'downloading', 'done']
const STEP_LABELS: Record<Step, string> = {
    'welcome': 'Welcome',
    'install-deps': 'Dependencies',
    'init-db': 'Database',
    'model-picker': 'Models',
    'downloading': 'Downloading',
    'done': 'Done',
}

const requiredModelIds = new Set(MODELS.filter(m => m.required).map(m => m.id))

interface Props {
    onComplete: () => void
}

export function SetupWizard({ onComplete }: Props) {
    const [step, setStep] = useState<Step>('welcome')
    const [selectedModels, setSelectedModels] = useState<Set<string>>(new Set(requiredModelIds))

    const advance = (to: Step) => setStep(to)

    const currentIndex = STEP_ORDER.indexOf(step)

    return (
        <div className="wizard-container">
            <div className="wizard-stepper">
                {STEP_ORDER.map((s, i) => (
                    <div
                        key={s}
                        className={[
                            'wizard-stepper__dot',
                            i < currentIndex ? 'wizard-stepper__dot--done' : '',
                            i === currentIndex ? 'wizard-stepper__dot--active' : '',
                        ].join(' ')}
                        title={STEP_LABELS[s]}
                    />
                ))}
            </div>

            <div className="wizard-content">
                {step === 'welcome' && (
                    <StepWelcome onContinue={() => advance('install-deps')} />
                )}
                {step === 'install-deps' && (
                    <StepInstallDeps onDone={() => advance('init-db')} />
                )}
                {step === 'init-db' && (
                    <StepInitDb onDone={() => advance('model-picker')} />
                )}
                {step === 'model-picker' && (
                    <StepModelPicker
                        selected={selectedModels}
                        onChange={setSelectedModels}
                        onContinue={() => advance('downloading')}
                    />
                )}
                {step === 'downloading' && (
                    <StepDownloading
                        selectedModels={selectedModels}
                        onDone={() => advance('done')}
                    />
                )}
                {step === 'done' && (
                    <StepDone onComplete={onComplete} />
                )}
            </div>
        </div>
    )
}
