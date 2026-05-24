import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import i18n from '@/i18n'
import { DuplicatesPage } from '../DuplicatesPage'

vi.mock('@/api/base', () => ({ getBaseUrl: async () => 'http://localhost:8000' }))

afterEach(() => { i18n.changeLanguage('en') })

describe('DuplicatesPage i18n', () => {
    it('renders Russian duplicates title', () => {
        i18n.changeLanguage('ru')
        render(<MemoryRouter><DuplicatesPage /></MemoryRouter>)
        expect(screen.getByRole('heading', { name: 'Дубликаты' })).toBeInTheDocument()
    })
})
