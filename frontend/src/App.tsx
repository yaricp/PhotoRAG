import React, { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Sidebar } from './components/ui/Sidebar'
import { Header } from './components/ui/Header'
import { AppRoutes } from './pages/AppRoutes'
import { SetupWizard } from './pages/SetupWizard'
import { TesseractBanner, TesseractStatus } from './components/ui/TesseractBanner'
import { PipelineWarningBanner } from './components/ui/PipelineWarningBanner'
import { EmbeddingReindexBanner } from './components/ui/EmbeddingReindexBanner'
import { getBaseUrl } from './api/base'
import { getSettings } from './api/client'
import './styles/global.css'

type SidebarState = 'full' | 'compact' | 'hidden'
type AppMode = 'loading' | 'wizard' | 'app'

// Synchronous check: no Electron → start in 'app' mode immediately (no flash of null).
const hasSetupCheck = typeof window !== 'undefined' && !!window.electronAPI?.checkSetupNeeded

export default function App() {
    const { i18n } = useTranslation()
    const [sidebarState, setSidebarState] = useState<SidebarState>('full')
    const [mode, setMode] = useState<AppMode>(hasSetupCheck ? 'loading' : 'app')
    const [tesseractStatus, setTesseractStatus] = useState<TesseractStatus | null>(null)

    useEffect(() => {
        if (!hasSetupCheck) return
        window.electronAPI.checkSetupNeeded().then(({ needed }) => {
            setMode(needed ? 'wizard' : 'app')
        })
    }, [])

    // Sync UI language from settings DB on startup
    useEffect(() => {
        getSettings()
            .then(s => {
                const lang = s['default_language']
                if (lang && lang !== i18n.language) i18n.changeLanguage(lang)
            })
            .catch(() => { /* backend not ready yet — keep default */ })
    }, [])

    // Fetch tesseract status once the main app is ready.
    useEffect(() => {
        if (mode !== 'app') return
        getBaseUrl().then(base =>
            fetch(`${base}/api/system/tesseract/`)
                .then(r => r.json())
                .then(setTesseractStatus)
                .catch(() => { /* backend not reachable — suppress */ })
        )
    }, [mode])

    const cycleSidebar = () => {
        setSidebarState(prev => {
            if (prev === 'full') return 'compact'
            if (prev === 'compact') return 'hidden'
            return 'full'
        })
    }

    if (mode === 'loading') {
        return null
    }

    if (mode === 'wizard') {
        return <SetupWizard onComplete={() => setMode('app')} />
    }

    return (
        <div className="app-layout">
            <TesseractBanner status={tesseractStatus} />
            <PipelineWarningBanner />
            <EmbeddingReindexBanner />
            <Header
                sidebarState={sidebarState}
                onToggleSidebar={cycleSidebar}
            />

            <div className="app-body">
                <Sidebar state={sidebarState} />

                <main className={`app-main app-main--${sidebarState}`}>
                    <AppRoutes />
                </main>
            </div>
        </div>
    )
}
