import React from 'react'
import { NavLink } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import './Sidebar.css'

type SidebarState = 'full' | 'compact' | 'hidden'

type Props = {
    state?: SidebarState
}

const links = [
    { to: '/', key: 'gallery', icon: '🖼️', end: true },
    { to: '/search', key: 'search', icon: '🔍' },
    { to: '/documents', key: 'documents', icon: '📄' },
    { to: '/duplicates', key: 'duplicates', icon: '⊕' },
    { to: '/garbage', key: 'garbage', icon: '🗑️' },
    { to: '/chat', key: 'chat', icon: '💬' },
    { to: '/processing', key: 'processing', icon: '📹' },
    { to: '/folders', key: 'folders', icon: '📁' },
    { to: '/models', key: 'models', icon: '🤖' },
    { to: '/prompts', key: 'prompts', icon: '📝' },
    { to: '/settings', key: 'settings', icon: '⚙️' },
]

const bottomLinks = [
    { to: '/help', key: 'help', icon: '❓' },
]

export function Sidebar({ state = 'full' }: Props) {
    const { t } = useTranslation()

    if (state === 'hidden') return null

    const renderLink = ({ to, key, icon, end }: { to: string; key: string; icon: string; end?: boolean }) => (
        <li key={to}>
            <NavLink
                to={to}
                end={end}
                className={({ isActive }) =>
                    `sidebar__link${isActive ? ' sidebar__link--active' : ''}`
                }
            >
                <span className="sidebar__icon">{icon}</span>
                {state === 'full' && (
                    <span className="sidebar__label">{t(`sidebar.${key}`)}</span>
                )}
            </NavLink>
        </li>
    )

    return (
        <nav className={`sidebar sidebar--${state}`} data-testid="sidebar">
            <div className="sidebar__content">
                <ul className="sidebar__nav">
                    {links.map(renderLink)}
                </ul>
                <div className="sidebar__separator" />
                <ul className="sidebar__nav">
                    {bottomLinks.map(renderLink)}
                </ul>
            </div>
        </nav>
    )
}