import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import App from '../App'

describe('App', () => {
    it('renders sidebar', () => {
        render(
            <MemoryRouter>
                <App />
            </MemoryRouter>
        )
        expect(screen.getByTestId('sidebar')).toBeInTheDocument()
    })

    it('renders main content area', () => {
        render(
            <MemoryRouter>
                <App />
            </MemoryRouter>
        )
        expect(screen.getByTestId('main-content')).toBeInTheDocument()
    })

    it('renders gallery page by default', () => {
        render(
            <MemoryRouter initialEntries={['/']}>
                <App />
            </MemoryRouter>
        )
        expect(screen.getByTestId('page-gallery')).toBeInTheDocument()
    })
})