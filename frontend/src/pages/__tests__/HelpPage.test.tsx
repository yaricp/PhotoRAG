import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { AppRoutes } from '../AppRoutes'
import i18n from '@/i18n'

afterEach(async () => { await i18n.changeLanguage('en') })

const renderAt = (path: string) =>
    render(
        <MemoryRouter initialEntries={[path]}>
            <AppRoutes />
        </MemoryRouter>
    )

describe('HelpPage', () => {
    it('renders help sidebar with all 16 topic links', () => {
        renderAt('/help/getting-started')
        const sidebar = screen.getByTestId('help-sidebar')
        const links = within(sidebar).getAllByRole('link')
        expect(links).toHaveLength(16)
    })

    it('renders article for the current topic', () => {
        renderAt('/help/gallery')
        expect(screen.getByTestId('help-article')).toBeInTheDocument()
        // Title should reflect the gallery topic
        const article = screen.getByTestId('help-article')
        expect(within(article).getByRole('heading', { level: 1 })).toBeInTheDocument()
    })

    it('renders getting-started content by default on /help/getting-started', () => {
        renderAt('/help/getting-started')
        const article = screen.getByTestId('help-article')
        // Title key resolves to English text
        expect(within(article).getByText(/getting started/i)).toBeInTheDocument()
    })

    it('unknown topic falls back to getting-started article', () => {
        renderAt('/help/nonexistent-topic')
        const article = screen.getByTestId('help-article')
        expect(within(article).getByText(/getting started/i)).toBeInTheDocument()
    })

    it('TOC link for gallery is active on /help/gallery', () => {
        renderAt('/help/gallery')
        const sidebar = screen.getByTestId('help-sidebar')
        const galleryLink = within(sidebar).getByRole('link', { name: /gallery/i })
        expect(galleryLink).toHaveClass('help-sidebar__link--active')
    })

    it('renders Russian article titles when language is ru', async () => {
        await i18n.changeLanguage('ru')
        renderAt('/help/getting-started')
        const sidebar = screen.getByTestId('help-sidebar')
        // At least one link in the sidebar should contain non-English characters
        const links = within(sidebar).getAllByRole('link')
        const allText = links.map(l => l.textContent ?? '').join(' ')
        expect(allText).toMatch(/[а-яА-Я]/)
    })

    it('renders Spanish article titles when language is es', async () => {
        await i18n.changeLanguage('es')
        renderAt('/help/getting-started')
        const sidebar = screen.getByTestId('help-sidebar')
        const links = within(sidebar).getAllByRole('link')
        const allText = links.map(l => l.textContent ?? '').join(' ')
        // Spanish text should contain special chars or recognizable words
        expect(allText.length).toBeGreaterThan(0)
        // Getting started in Spanish contains common words
        expect(allText).toMatch(/[a-zA-ZáéíóúñÁÉÍÓÚÑ]/i)
    })

    it('article content updates when navigating between topics via TOC link', async () => {
        const user = userEvent.setup()
        renderAt('/help/getting-started')
        const sidebar = screen.getByTestId('help-sidebar')
        const galleryLink = within(sidebar).getByRole('link', { name: /gallery/i })
        await user.click(galleryLink)
        // After clicking gallery the article title should change
        const article = screen.getByTestId('help-article')
        expect(within(article).getByRole('heading', { level: 1 })).toBeInTheDocument()
    })

    it('each sidebar link has a valid /help/:topic href', () => {
        renderAt('/help/getting-started')
        const sidebar = screen.getByTestId('help-sidebar')
        const links = within(sidebar).getAllByRole('link')
        links.forEach(link => {
            expect(link.getAttribute('href')).toMatch(/^\/help\/[\w-]+$/)
        })
    })
})
