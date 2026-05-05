import React from 'react'
import { NavLink } from 'react-router-dom'
import './Sidebar.css'

type SidebarState = 'full' | 'compact' | 'hidden'

type Props = {
    state: SidebarState
    onCycle: () => void
}

const links = [
    { to: '/', label: 'Gallery', icon: '🖼️', end: true },
    { to: '/search', label: 'Search', icon: '🔍' },
    { to: '/documents', label: 'Documents', icon: '📄' },
    { to: '/chat', label: 'Chat', icon: '💬' },
    { to: '/settings', label: 'Settings', icon: '⚙️' },
]

export function Sidebar({ state, onCycle }: Props) {
    return (
        <nav className={`sidebar sidebar--${state}`}>

            {/* ВСЕГДА ВИДНА */}
            <button className="sidebar__toggle" onClick={onCycle}>
                {state === 'hidden' ? '➡️' : '⬅️'}
            </button>

            {/* СКРЫВАЕМ СОДЕРЖИМОЕ, НО НЕ КОМПОНЕНТ */}
            <div className="sidebar__content">
                <div className="sidebar__logo">
                    {state === 'compact' ? 'PD' : 'Photo Describer'}
                </div>

                <ul className="sidebar__nav">
                    {links.map(({ to, label, icon, end }) => (
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
                                    <span className="sidebar__label">{label}</span>
                                )}
                            </NavLink>
                        </li>
                    ))}
                </ul>
            </div>
        </nav>
    )
}