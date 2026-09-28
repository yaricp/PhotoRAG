export interface OllamaDownloadState {
    phase: 'checking' | 'downloading' | 'ready' | 'error'
    status: string
    completed: number
    total: number
    error?: string
}

let states: Record<string, OllamaDownloadState> = {}
const listeners = new Set<() => void>()
const active = new Map<string, Promise<void>>()
let unsubscribeProgress: (() => void) | undefined

export function ollamaDownloadKey(model: string, url?: string): string {
    return `${new URL(url?.trim() || 'http://localhost:11434').origin}/${model.trim()}`
}

export function getOllamaDownloadStates(): Record<string, OllamaDownloadState> {
    return states
}

export function subscribeOllamaDownloads(listener: () => void): () => void {
    listeners.add(listener)
    return () => { listeners.delete(listener) }
}

function update(key: string, state: OllamaDownloadState): void {
    states = { ...states, [key]: state }
    for (const listener of listeners) listener()
}

function listenForProgress(): void {
    if (unsubscribeProgress) return
    unsubscribeProgress = window.electronAPI.onOllamaPullProgress(({ model, status, completed, total, done }) => {
        for (const [key] of active) {
            if (!key.endsWith(`/${model}`)) continue
            update(key, { phase: done ? 'ready' : 'downloading', status, completed, total })
        }
    })
}

/** One check/pull per local server and model, shared by all model settings cards. */
export function ensureOllamaModel(model: string, url?: string): Promise<void> {
    const name = model.trim()
    const key = ollamaDownloadKey(name, url)
    const existing = active.get(key)
    if (existing) return existing

    listenForProgress()
    update(key, { phase: 'checking', status: '', completed: 0, total: 0 })
    const operation = (async () => {
        try {
            const installed = await window.electronAPI.listOllamaModels(url)
            if (!installed.includes(name) && !installed.includes(`${name}:latest`)) {
                update(key, { phase: 'downloading', status: '', completed: 0, total: 0 })
                await window.electronAPI.pullOllamaModel({ model: name, url })
            }
            update(key, { phase: 'ready', status: '', completed: 0, total: 0 })
        } catch (cause) {
            update(key, { phase: 'error', status: '', completed: 0, total: 0, error: String(cause) })
            throw cause
        } finally {
            active.delete(key)
            if (active.size === 0) {
                unsubscribeProgress?.()
                unsubscribeProgress = undefined
            }
        }
    })()
    active.set(key, operation)
    return operation
}
