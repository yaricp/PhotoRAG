import React, { useState, useEffect } from 'react'
import { Sidebar } from './components/ui/Sidebar'
import { Header } from './components/ui/Header'
import { AppRoutes } from './pages/AppRoutes'
import { SetupWizard } from './pages/SetupWizard'
import './styles/global.css'

type SidebarState = 'full' | 'compact' | 'hidden'
type AppMode = 'loading' | 'wizard' | 'app'

// Synchronous check: no Electron → start in 'app' mode immediately (no flash of null).
const hasSetupCheck = typeof window !== 'undefined' && !!window.electronAPI?.checkSetupNeeded

export default function App() {
    const [sidebarState, setSidebarState] = useState<SidebarState>('full')
    const [mode, setMode] = useState<AppMode>(hasSetupCheck ? 'loading' : 'app')

    useEffect(() => {
        if (!hasSetupCheck) return
        window.electronAPI.checkSetupNeeded().then(({ needed }) => {
            setMode(needed ? 'wizard' : 'app')
        })
    }, [])

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
