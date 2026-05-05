import React, { useState } from 'react'
import { Sidebar } from './components/ui/Sidebar'
import { AppRoutes } from './pages/AppRoutes'
import './styles/global.css'

type SidebarState = 'full' | 'compact' | 'hidden'

export default function App() {
    const [sidebarState, setSidebarState] = useState<SidebarState>('full')

    const cycleSidebar = () => {
        setSidebarState(prev => {
            if (prev === 'full') return 'compact'
            if (prev === 'compact') return 'hidden'
            return 'full'
        })
    }

    return (
        <div className="app-layout">
            <Sidebar
                state={sidebarState}
                onCycle={cycleSidebar}
            />

            <main
                data-testid="main-content"
                className={`app-main app-main--${sidebarState}`}
            >
                <AppRoutes />
            </main>
        </div>
    )
}