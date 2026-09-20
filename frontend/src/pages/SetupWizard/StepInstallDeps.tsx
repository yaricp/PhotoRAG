import React, { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

interface Props {
    onDone: () => void
}

interface InstallProgress {
    line: string
    percent: number
    phase?: string
    installedCount?: number
    totalCount?: number
    latestInstalled?: string
    latestPackage?: string
}

export function StepInstallDeps({ onDone }: Props) {
    const { t } = useTranslation()
    const [installing, setInstalling] = useState(false)
    const [progress, setProgress] = useState(0)
    const [logLine, setLogLine] = useState('')
    const [installProgress, setInstallProgress] = useState<InstallProgress | null>(null)
    const [lastActivity, setLastActivity] = useState('')
    const [error, setError] = useState<string | null>(null)
    const startedRef = useRef(false)

    useEffect(() => {
        window.electronAPI.onInstallDepsProgress((data) => {
            setProgress(data.percent)
            setLogLine(data.line)
            setInstallProgress(data)
            setLastActivity(new Date().toLocaleTimeString())
        })
    }, [])

    const isInstallingPackages = installProgress?.phase === 'installing-packages'

    const handleInstall = async () => {
        if (startedRef.current) return
        startedRef.current = true
        setInstalling(true)
        setError(null)
        try {
            await window.electronAPI.installDeps()
            onDone()
        } catch (e) {
            startedRef.current = false
            setError(String(e))
            setInstalling(false)
        }
    }

    return (
        <div className="wizard-step">
            <h2>{t('wizard.stepInstallDeps.title')}</h2>
            <p>{t('wizard.stepInstallDeps.subtitle')}</p>

            {!installing && !error && (
                <div className="wizard-actions">
                    <button
                        className="wizard-btn wizard-btn--primary"
                        onClick={handleInstall}
                        disabled={installing}
                    >
                        {t('wizard.stepInstallDeps.installButton')}
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
                        className={`wizard-progressbar${isInstallingPackages ? ' wizard-progressbar--active' : ''}`}
                    >
                        <div
                            className={`wizard-progressbar__fill${isInstallingPackages ? ' wizard-progressbar__fill--active' : ''}`}
                            style={{ width: `${progress}%` }}
                        />
                    </div>
                    {logLine && <p className="wizard-log">{logLine}</p>}
                    {isInstallingPackages && (
                        <div className="wizard-progress-detail wizard-progress-detail--active" aria-live="polite">
                            <p className="wizard-progress-detail__status">{t('wizard.stepInstallDeps.installingPackagesActive')}</p>
                            <p>
                                {t('wizard.stepInstallDeps.installingPackages', {
                                    installed: installProgress.installedCount ?? 0,
                                    total: installProgress.totalCount ?? '?',
                                })}
                            </p>
                            {(installProgress.latestInstalled || installProgress.latestPackage) && (
                                <p>{t('wizard.stepInstallDeps.latestInstalled', { packageName: installProgress.latestInstalled ?? installProgress.latestPackage })}</p>
                            )}
                            {lastActivity && (
                                <p>{t('wizard.stepInstallDeps.lastActivity', { time: lastActivity })}</p>
                            )}
                            <p>{t('wizard.stepInstallDeps.installingPackagesHint')}</p>
                        </div>
                    )}
                </div>
            )}

            {error && (
                <div className="wizard-error">
                    <p>{t('wizard.stepInstallDeps.errorMessage', { error })}</p>
                    <button
                        className="wizard-btn wizard-btn--primary"
                        onClick={handleInstall}
                    >
                        {t('wizard.stepInstallDeps.retryButton')}
                    </button>
                </div>
            )}
        </div>
    )
}
