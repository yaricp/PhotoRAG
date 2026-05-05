import React from 'react'
import { Sidebar } from './components/ui/Sidebar'
import { AppRoutes } from './pages/AppRoutes'
import './styles/global.css'

export default function App() {
    return (
        <div style={{ display: 'flex', minHeight: '100vh' }}>
            <Sidebar />
            <main
                data-testid="main-content"
                style={{ flex: 1, overflow: 'auto' }}
            >
                <AppRoutes />
            </main>
        </div>
    )
}