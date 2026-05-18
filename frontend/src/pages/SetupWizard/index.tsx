import React, { useState } from 'react'
import { StepWelcome } from './StepWelcome'
import { StepInstallDeps } from './StepInstallDeps'
import { StepInitDb } from './StepInitDb'
import { StepModelConfig } from './StepModelConfig'
import { StepDownloading } from './StepDownloading'
import { StepDone } from './StepDone'
import { MODELS } from './models'
import './SetupWizard.css'

type Step = 'welcome' | 'install-deps' | 'init-db' | 'model-config' | 'downloading' | 'done'

const STEP_ORDER: Step[] = ['welcome', 'install-deps', 'init-db', 'model-config', 'downloading', 'done']
const STEP_LABELS: Record<Step, string> = {
    'welcome':      'Welcome',
    'install-deps': 'Dependencies',
    'init-db':      'Database',
    'model-config': 'AI Models',
    'downloading':  'Downloading',
    'done':         'Done',
}

interface ModelConfig {
    id: number
    type: string
    mode: 'local' | 'remote'
    model_name: string
    url?: string
    api_key?: string
    model_provider?: string
    similarity_limit?: number
}

// DB type 'translator' maps to models.ts id 'translation'
function dbTypeToModelId(dbType: string): string {
    if (dbType === 'translator') return 'translation'
    return dbType
}

interface Props {
    onComplete: () => void
}

export function SetupWizard({ onComplete }: Props) {
    const [step, setStep] = useState<Step>('welcome')
    const [selectedModels, setSelectedModels] = useState<Set<string>>(new Set())

    const advance = (to: Step) => setStep(to)

    const currentIndex = STEP_ORDER.indexOf(step)

    // Models not selected for local download → written as *_MODE=remote in .env
    const skippedModels = MODELS
        .filter(m => !selectedModels.has(m.id))
        .map(m => m.id)

    const handleModelConfigDone = (configs: ModelConfig[]) => {
        const localIds = new Set(
            configs
                .filter(c => c.mode === 'local')
                .map(c => dbTypeToModelId(c.type))
        )
        // Downloadable = models that exist in the MODELS download list AND are local
        const downloadable = new Set(MODELS.filter(m => localIds.has(m.id)).map(m => m.id))
        setSelectedModels(downloadable)

        if (downloadable.size === 0) {
            advance('done')
        } else {
            advance('downloading')
        }
    }

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
                    <StepInitDb onDone={() => advance('model-config')} />
                )}
                {step === 'model-config' && (
                    <StepModelConfig onDone={handleModelConfigDone} />
                )}
                {step === 'downloading' && (
                    <StepDownloading
                        selectedModels={selectedModels}
                        onDone={() => advance('done')}
                    />
                )}
                {step === 'done' && (
                    <StepDone
                        skippedModels={skippedModels}
                        onComplete={onComplete}
                    />
                )}
            </div>
        </div>
    )
}
