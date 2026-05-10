import React from 'react'
import { NavLink } from 'react-router-dom'
import './Sidebar.css'

type SidebarState = 'full' | 'compact' | 'hidden'

type Props = {
    state?: SidebarState
}

const links = [
    { to: '/', label: 'Gallery', icon: '🖼️', end: true },
    { to: '/search', label: 'Search', icon: '🔍' },
    { to: '/documents', label: 'Documents', icon: '📄' },
    { to: '/duplicates', label: 'Duplicates', icon: '⊕' },
    { to: '/garbage', label: 'Garbage', icon: '🗑️' },
    { to: '/chat', label: 'Agent AI(Chat)', icon: '💬' },
    { to: '/processing', label: 'Processing', icon: '📹' },
    { to: '/folders', label: 'Folders', icon: '📁' },
    { to: '/models', label: 'Models', icon: '🤖' },
    { to: '/settings', label: 'Settings', icon: '⚙️' },
]

export function Sidebar({ state = 'full' }: Props) {
    if (state === 'hidden') return null

    return (
        <nav className={`sidebar sidebar--${state}`}>

            <div className="sidebar__content">
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