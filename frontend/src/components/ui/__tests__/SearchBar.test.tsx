import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SearchBar } from '../SearchBar'

describe('SearchBar', () => {
    it('renders input', () => {
        render(<SearchBar onSearch={vi.fn()} />)
        expect(screen.getByRole('searchbox')).toBeInTheDocument()
    })

    it('calls onSearch when Enter pressed', async () => {
        const onSearch = vi.fn()
        render(<SearchBar onSearch={onSearch} />)
        await userEvent.type(screen.getByRole('searchbox'), 'invoice{Enter}')
        expect(onSearch).toHaveBeenCalledWith('invoice')
    })

    it('does not call onSearch on empty Enter', async () => {
        const onSearch = vi.fn()
        render(<SearchBar onSearch={onSearch} />)
        await userEvent.type(screen.getByRole('searchbox'), '{Enter}')
        expect(onSearch).not.toHaveBeenCalled()
    })

    it('shows clear button when value present', async () => {
        render(<SearchBar onSearch={vi.fn()} />)
        await userEvent.type(screen.getByRole('searchbox'), 'hello')
        expect(screen.getByTestId('search-clear')).toBeInTheDocument()
    })

    it('clears input when clear button clicked', async () => {
        const onSearch = vi.fn()
        render(<SearchBar onSearch={onSearch} />)
        await userEvent.type(screen.getByRole('searchbox'), 'hello')
        await userEvent.click(screen.getByTestId('search-clear'))
        expect(screen.getByRole('searchbox')).toHaveValue('')
    })

    it('shows placeholder text', () => {
        render(<SearchBar onSearch={vi.fn()} placeholder="Search photos..." />)
        expect(screen.getByPlaceholderText('Search photos...')).toBeInTheDocument()
    })
})