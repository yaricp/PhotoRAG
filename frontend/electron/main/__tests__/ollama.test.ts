import { afterEach, describe, expect, it, vi } from 'vitest'
import { deleteOllamaModel, listOllamaModels, pullOllamaModel } from '../ollama'

afterEach(() => vi.restoreAllMocks())

describe('local Ollama API integration', () => {
    it('streams pull progress and waits for success', async () => {
        const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async input => {
            const url = String(input)
            if (url.endsWith('/api/version')) return { ok: true } as Response
            const encoder = new TextEncoder()
            const body = new ReadableStream<Uint8Array>({
                start(controller) {
                    controller.enqueue(encoder.encode('{"status":"pulling model","total":100,"completed":50}\n'))
                    controller.enqueue(encoder.encode('{"status":"success"}\n'))
                    controller.close()
                },
            })
            return { ok: true, body } as Response
        })
        const progress: Array<{ status: string; done: boolean }> = []
        await pullOllamaModel('gemma3:4b', undefined, item => progress.push(item))
        expect(progress).toEqual([
            expect.objectContaining({ status: 'pulling model', completed: 50, total: 100, done: false }),
            expect.objectContaining({ status: 'success', done: true }),
        ])
        expect(fetchMock).toHaveBeenCalledWith('http://localhost:11434/api/pull', expect.objectContaining({
            method: 'POST', body: JSON.stringify({ model: 'gemma3:4b', stream: true }),
        }))
    })

    it('reports an Ollama pull failure instead of completing the download', async () => {
        vi.spyOn(globalThis, 'fetch').mockImplementation(async input => {
            if (String(input).endsWith('/api/version')) return { ok: true } as Response
            const body = new ReadableStream<Uint8Array>({
                start(controller) {
                    controller.enqueue(new TextEncoder().encode('{"error":"not enough disk space"}\n'))
                    controller.close()
                },
            })
            return { ok: true, body } as Response
        })
        await expect(pullOllamaModel('gemma3:4b', undefined, vi.fn())).rejects.toThrow('not enough disk space')
    })

    it('reads installed models and deletes only the named model', async () => {
        const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async input => {
            const url = String(input)
            if (url.endsWith('/api/tags')) return { ok: true, json: async () => ({ models: [{ name: 'gemma3:4b' }] }) } as Response
            return { ok: true } as Response
        })
        expect(await listOllamaModels()).toEqual(['gemma3:4b'])
        await deleteOllamaModel('gemma3:4b')
        expect(fetchMock).toHaveBeenCalledWith('http://localhost:11434/api/delete', expect.objectContaining({
            method: 'DELETE', body: JSON.stringify({ model: 'gemma3:4b' }),
        }))
    })

    it('refuses model-management calls to a nonlocal URL', async () => {
        const fetchMock = vi.spyOn(globalThis, 'fetch')
        await expect(listOllamaModels('https://example.com')).rejects.toThrow(/local server URL/)
        expect(fetchMock).not.toHaveBeenCalled()
    })
})
