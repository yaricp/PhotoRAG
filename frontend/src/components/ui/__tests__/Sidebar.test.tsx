import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Sidebar } from '../Sidebar'

const renderSidebar = (path = '/') =>
    render(
        <MemoryRouter initialEntries={[path]}>
            <Sidebar />
        </MemoryRouter>
    )

describe('Sidebar', () => {
    it('renders all nav links', () => {
        renderSidebar()
        expect(screen.getByText('Gallery')).toBeInTheDocument()
        expect(screen.getByText('Search')).toBeInTheDocument()
        expect(screen.getByText('Documents')).toBeInTheDocument()
        expect(screen.getByText('Chat')).toBeInTheDocument()
        expect(screen.getByText('Settings')).toBeInTheDocument()
    })

    it('highlights Gallery link on / route', () => {
        renderSidebar('/')
        expect(screen.getByText('Gallery').closest('a')).toHaveClass('sidebar__link--active')
    })

    it('highlights Search link on /search route', () => {
        renderSidebar('/search')
        expect(screen.getByText('Search').closest('a')).toHaveClass('sidebar__link--active')
    })

    it('highlights Settings link on /settings route', () => {
        renderSidebar('/settings')
        expect(screen.getByText('Settings').closest('a')).toHaveClass('sidebar__link--active')
    })

    it('does not highlight Gallery when on /search', () => {
        renderSidebar('/search')
        expect(screen.getByText('Gallery').closest('a')).not.toHaveClass('sidebar__link--active')
    })
})