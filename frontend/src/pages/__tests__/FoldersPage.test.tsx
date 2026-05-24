import { describe, it, expect, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import i18n from '@/i18n'
import { FoldersPage } from '../FoldersPage'

vi.mock('@/api/base', () => ({ getBaseUrl: async () => 'http://localhost:8000' }))

afterEach(() => { i18n.changeLanguage('en') })

describe('FoldersPage i18n', () => {
    it('renders Russian folders title', () => {
        i18n.changeLanguage('ru')
        render(<MemoryRouter><FoldersPage /></MemoryRouter>)
        expect(screen.getByRole('heading', { name: 'Папки' })).toBeInTheDocument()
    })
})
