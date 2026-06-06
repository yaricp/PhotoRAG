import React from 'react'
import { useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import './Header.css'
import icon from '../../assets/icon.png'

type SidebarState = 'full' | 'compact' | 'hidden'

type Props = {
    sidebarState: SidebarState
    onToggleSidebar: () => void
}

const ROUTE_KEYS: { path: string; key: string }[] = [
    { path: '/',            key: 'sidebar.gallery' },
    { path: '/search',      key: 'search.title' },
    { path: '/documents',   key: 'documents.title' },
    { path: '/duplicates',  key: 'duplicates.title' },
    { path: '/garbage',     key: 'garbage.title' },
    { path: '/chat',        key: 'chat.title' },
    { path: '/processing',  key: 'processing.title' },
    { path: '/folders',     key: 'folders.title' },
    { path: '/models',      key: 'models.title' },
    { path: '/prompts',     key: 'prompts.title' },
    { path: '/settings',    key: 'settings.title' },
]

export function Header({ sidebarState, onToggleSidebar }: Props) {
    const location = useLocation()
    const { t } = useTranslation()

    const current = ROUTE_KEYS.find(r => location.pathname === r.path)

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

            <div className="app-header__logo">
                <img src={icon} alt="PhotoRAG" className="app-header__logo-img" />
                <span className="app-header__logo-name">PhotoRAG</span>
            </div>

            <div className="app-header__title">
                {current ? t(current.key) : ''}
            </div>

        </header>
    )
}
