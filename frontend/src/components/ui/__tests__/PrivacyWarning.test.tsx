import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18n from '@/i18n'
import { PrivacyWarning } from '../PrivacyWarning'

afterEach(() => { i18n.changeLanguage('en') })

describe('PrivacyWarning', () => {
    it('renders compact state by default with no modal', () => {
        render(<PrivacyWarning />)
        expect(screen.getByText(/Privacy Notice/)).toBeInTheDocument()
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })

    it('"Show Full Warning" button opens modal with full title', async () => {
        render(<PrivacyWarning />)
        await userEvent.click(screen.getByRole('button', { name: /Show Full Warning/i }))
        const dialog = screen.getByRole('dialog')
        expect(dialog).toBeInTheDocument()
        expect(within(dialog).getByRole('heading')).toHaveTextContent(/Remote AI Models/i)
    })

    it('Close button dismisses the modal', async () => {
        render(<PrivacyWarning />)
        await userEvent.click(screen.getByRole('button', { name: /Show Full Warning/i }))
        const dialog = screen.getByRole('dialog')
        await userEvent.click(within(dialog).getByRole('button', { name: /^Close$/i }))
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })

    it('renders in Russian', () => {
        i18n.changeLanguage('ru')
        render(<PrivacyWarning />)
        expect(screen.getByText(/Конфиденциальность/)).toBeInTheDocument()
    })

    it('Russian modal opens with full Russian title', async () => {
        i18n.changeLanguage('ru')
        render(<PrivacyWarning />)
        await userEvent.click(screen.getByRole('button', { name: /Показать полное предупреждение/i }))
        const dialog = screen.getByRole('dialog')
        expect(dialog).toBeInTheDocument()
        expect(within(dialog).getByRole('heading')).toHaveTextContent(/Конфиденциальность/i)
    })

    it('renders in Spanish', () => {
        i18n.changeLanguage('es')
        render(<PrivacyWarning />)
        expect(screen.getByText(/privacidad/i)).toBeInTheDocument()
    })
})
