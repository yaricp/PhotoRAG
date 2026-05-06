import React from 'react'
import { useLocation } from 'react-router-dom'
import './Header.css'

type SidebarState = 'full' | 'compact' | 'hidden'

type Props = {
    sidebarState: SidebarState
    onToggleSidebar: () => void
}

const routes = [
    { path: '/', label: 'Gallery' },
    { path: '/search', label: 'Semantic Photo Search' },
    { path: '/documents', label: 'Documents' },
    { path: '/chat', label: 'Chat AI' },
    { path: '/processing', label: 'Video Processing' },
    { path: '/watchers', label: 'Watchers' },
    { path: '/models', label: 'Models' },
    { path: '/settings', label: 'Settings' },
]

export function Header({ sidebarState, onToggleSidebar }: Props) {
    const location = useLocation()

    const current = routes.find(r => location.pathname === r.path)

    const getIcon = () => {
        switch (sidebarState) {
            case 'full':
                return '⟨⟨' // collapse
            case 'compact':
                return '⟨⟨' // expand/collapse toggle
            case 'hidden':
                return '☰' // open menu
        }
    }

    return (
        <header className="app-header">

            <div className="app-header__left">
                <button
                    className="app-header__toggle"
                    onClick={onToggleSidebar}
                >
                    {getIcon()}
                </button>
            </div>

            {/* TODO: Add logo here */}

            <div className="app-header__title">
                {current?.label || 'Photo Describer'}
            </div>

        </header>
    )
}