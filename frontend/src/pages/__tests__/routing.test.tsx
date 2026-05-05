import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { AppRoutes } from '../AppRoutes'

const renderAt = (path: string) =>
    render(
        <MemoryRouter initialEntries={[path]}>
            <AppRoutes />
        </MemoryRouter>
    )

describe('routing', () => {
    it('/ renders GalleryPage', () => {
        renderAt('/')
        expect(screen.getByTestId('page-gallery')).toBeInTheDocument()
    })

    it('/search renders SearchPage', () => {
        renderAt('/search')
        expect(screen.getByTestId('page-search')).toBeInTheDocument()
    })

    it('/documents renders DocumentsPage', () => {
        renderAt('/documents')
        expect(screen.getByTestId('page-documents')).toBeInTheDocument()
    })

    it('/chat renders ChatPage', () => {
        renderAt('/chat')
        expect(screen.getByTestId('page-chat')).toBeInTheDocument()
    })

    it('/settings renders SettingsPage', () => {
        renderAt('/settings')
        expect(screen.getByTestId('page-settings')).toBeInTheDocument()
    })

    it('/photo/:id renders PhotoDetailPage', () => {
        renderAt('/photo/42')
        expect(screen.getByTestId('page-photo-detail')).toBeInTheDocument()
    })
})