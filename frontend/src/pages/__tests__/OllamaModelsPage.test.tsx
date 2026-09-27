import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { OllamaModelsPage } from '../OllamaModelsPage'

vi.mock('@/api/client', () => ({
    getModelConfigs: vi.fn().mockResolvedValue([
        { id: 1, type: 'chat', mode: 'remote', model_provider: 'ollama', model_name: 'gemma3:4b' },
    ]),
}))

const inventory = {
    models: [
        { name: 'gemma3:4b', size: 3_500_000_000, digest: 'one' },
        { name: 'nomic-embed-text:latest', size: 300_000_000, digest: 'two' },
    ],
    storagePath: '/home/user/.ollama/models',
    storageVerified: true,
    freeBytes: 2 * 1024 ** 3,
    totalBytes: 100 * 1024 ** 3,
}

const getOllamaInventory = vi.fn().mockResolvedValue(inventory)
const deleteOllamaModel = vi.fn().mockResolvedValue(undefined)

beforeEach(() => {
    vi.clearAllMocks()
    getOllamaInventory.mockResolvedValue(inventory)
    deleteOllamaModel.mockResolvedValue(undefined)
    Object.defineProperty(window, 'electronAPI', {
        configurable: true,
        value: { getOllamaInventory, deleteOllamaModel },
    })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
})

describe('OllamaModelsPage', () => {
    it('shows installed models, their sizes and low disk space', async () => {
        render(<OllamaModelsPage />)
        expect(await screen.findByText('gemma3:4b')).toBeInTheDocument()
        expect(screen.getByText('nomic-embed-text:latest')).toBeInTheDocument()
        expect(screen.getByText(/Free space on model disk/)).toHaveTextContent('2.0 GB')
        expect(screen.getByText(/Disk space is low/)).toBeInTheDocument()
        expect(screen.getByText(/Used by PhotoRAG: Chat/)).toBeInTheDocument()
    })

    it('deletes a selected model only after confirmation', async () => {
        render(<OllamaModelsPage />)
        await screen.findByText('gemma3:4b')
        fireEvent.click(screen.getAllByRole('button', { name: 'Delete' })[1])
        await waitFor(() => expect(deleteOllamaModel).toHaveBeenCalledWith({ model: 'nomic-embed-text:latest' }))
        expect(getOllamaInventory).toHaveBeenCalledTimes(2)
    })

    it('deletes every installed model when requested', async () => {
        render(<OllamaModelsPage />)
        await screen.findByText('gemma3:4b')
        fireEvent.click(screen.getByRole('button', { name: 'Delete all models' }))
        await waitFor(() => expect(deleteOllamaModel).toHaveBeenCalledTimes(2))
        expect(deleteOllamaModel).toHaveBeenNthCalledWith(1, { model: 'gemma3:4b' })
        expect(deleteOllamaModel).toHaveBeenNthCalledWith(2, { model: 'nomic-embed-text:latest' })
    })
})
