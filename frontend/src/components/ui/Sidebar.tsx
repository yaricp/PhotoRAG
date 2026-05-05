import React from 'react'
import { NavLink } from 'react-router-dom'
import './Sidebar.css'

const links = [
    { to: '/', label: 'Gallery', end: true },
    { to: '/search', label: 'Search' },
    { to: '/documents', label: 'Documents' },
    { to: '/chat', label: 'Chat' },
    { to: '/settings', label: 'Settings' },
]

export function Sidebar() {
    return (
        <nav className="sidebar" data-testid="sidebar">
            <div className="sidebar__logo">Photo Describer</div>
            <ul className="sidebar__nav">
                {links.map(({ to, label, end }) => (
                    <li key={to}>
                        <NavLink
                            to={to}
                            end={end}
                            className={({ isActive }) =>
                                `sidebar__link${isActive ? ' sidebar__link--active' : ''}`
                            }
                        >
                            {label}
                        </NavLink>
                    </li>
                ))}
            </ul>
        </nav>
    )
}