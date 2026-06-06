import React from 'react'
import { NavLink } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { HELP_TOPICS } from './topics'

interface Props {
    currentTopic: string
}

export function HelpSidebar({ currentTopic: _currentTopic }: Props) {
    const { t } = useTranslation()

    return (
        <nav className="help-sidebar" data-testid="help-sidebar">
            <h2 className="help-sidebar__title">{t('help.title')}</h2>
            <ul className="help-sidebar__list">
                {HELP_TOPICS.map(({ id }) => (
                    <li key={id}>
                        <NavLink
                            to={`/help/${id}`}
                            className={({ isActive }) =>
                                `help-sidebar__link${isActive ? ' help-sidebar__link--active' : ''}`
                            }
                        >
                            {t(`help.topics.${id}.title`)}
                        </NavLink>
                    </li>
                ))}
            </ul>
        </nav>
    )
}
