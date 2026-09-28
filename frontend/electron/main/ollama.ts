import { spawn } from 'child_process'
import { existsSync, statfsSync } from 'fs'
import { homedir } from 'os'
import { dirname, join } from 'path'

export interface OllamaPullProgress {
    model: string
    status: string
    completed: number
    total: number
    done: boolean
}

interface ActivePull {
    controller: AbortController
    promise: Promise<void>
    listeners: Set<(progress: OllamaPullProgress) => void>
    lastProgress?: OllamaPullProgress
}

const pulls = new Map<string, ActivePull>()
const DEFAULT_URL = 'http://localhost:11434'

export interface OllamaInventory {
    models: Array<{ name: string; size: number; digest: string }>
    storagePath: string | null
    freeBytes: number | null
    totalBytes: number | null
    storageVerified: boolean
}

function localBaseUrl(value?: string): string {
    const url = new URL(value?.trim() || DEFAULT_URL)
    if (url.protocol !== 'http:' || !['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)) {
        throw new Error('Automatic Ollama downloads require a local server URL (localhost).')
    }
    return url.origin
}

function ollamaExecutable(): string {
    if (process.platform === 'win32' && process.env.LOCALAPPDATA) {
        const installed = join(process.env.LOCALAPPDATA, 'Programs', 'Ollama', 'ollama.exe')
        if (existsSync(installed)) return installed
    }
    return 'ollama'
}

async function ensureServer(baseUrl: string): Promise<void> {
    try {
        if ((await fetch(`${baseUrl}/api/version`, { signal: AbortSignal.timeout(2500) })).ok) return
    } catch { /* Try to start the separately installed Ollama service. */ }

    const server = spawn(ollamaExecutable(), ['serve'], {
        detached: true,
        stdio: 'ignore',
        windowsHide: true,
    })
    server.on('error', () => {})
    server.unref()
    for (let attempt = 0; attempt < 20; attempt++) {
        await new Promise(resolve => setTimeout(resolve, 500))
        try {
            if ((await fetch(`${baseUrl}/api/version`, { signal: AbortSignal.timeout(1500) })).ok) return
        } catch { /* Server is still starting. */ }
    }
    throw new Error('Ollama is not available. Install and start Ollama, then retry.')
}

export async function listOllamaModels(url?: string): Promise<string[]> {
    const baseUrl = localBaseUrl(url)
    await ensureServer(baseUrl)
    const response = await fetch(`${baseUrl}/api/tags`)
    if (!response.ok) throw new Error(`Ollama model list failed (${response.status}).`)
    const data = await response.json() as { models?: Array<{ name: string }> }
    return (data.models ?? []).map(model => model.name)
}

export async function getOllamaInventory(url?: string): Promise<OllamaInventory> {
    const baseUrl = localBaseUrl(url)
    await ensureServer(baseUrl)
    const response = await fetch(`${baseUrl}/api/tags`)
    if (!response.ok) throw new Error(`Ollama model list failed (${response.status}).`)
    const data = await response.json() as { models?: Array<{ name: string; size: number; digest: string }> }
    const models = data.models ?? []
    let storagePath = process.env.OLLAMA_MODELS ||
        (process.platform === 'linux' ? '/usr/share/ollama/.ollama/models' : join(homedir(), '.ollama', 'models'))
    let storageVerified = false

    // Ollama's model info exposes a local blob path, including a custom OLLAMA_MODELS folder.
    if (models.length > 0) {
        try {
            const show = await fetch(`${baseUrl}/api/show`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ model: models[0].name }),
            })
            const info = await show.json() as { modelfile?: string }
            const from = info.modelfile?.match(/^FROM\s+(.+)$/m)?.[1]?.trim()
            if (from && existsSync(from)) {
                storagePath = dirname(dirname(from))
                storageVerified = true
            }
        } catch { /* The default location is still useful as an estimate. */ }
    }
    let freeBytes: number | null = null
    let totalBytes: number | null = null
    if (existsSync(storagePath)) {
        try {
            const disk = statfsSync(storagePath)
            freeBytes = disk.bavail * disk.bsize
            totalBytes = disk.blocks * disk.bsize
        } catch { /* The model directory may not be readable by this account. */ }
    }
    return { models, storagePath: existsSync(storagePath) ? storagePath : null,
        freeBytes, totalBytes, storageVerified }
}

export async function deleteOllamaModel(model: string, url?: string): Promise<void> {
    const baseUrl = localBaseUrl(url)
    await ensureServer(baseUrl)
    const response = await fetch(`${baseUrl}/api/delete`, {
        method: 'DELETE', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model }),
    })
    if (!response.ok) throw new Error(`Could not delete ${model}: ${await response.text()}`)
}

export function pullOllamaModel(
    model: string,
    url: string | undefined,
    onProgress: (progress: OllamaPullProgress) => void,
): Promise<void> {
    const name = model.trim()
    if (!name || !/^[\w./:-]+$/.test(name)) return Promise.reject(new Error('Select a valid Ollama model name.'))
    let baseUrl: string
    try {
        baseUrl = localBaseUrl(url)
    } catch (cause) {
        return Promise.reject(cause)
    }
    const key = `${baseUrl}/${name}`
    const existing = pulls.get(key)
    if (existing) {
        existing.listeners.add(onProgress)
        if (existing.lastProgress) onProgress(existing.lastProgress)
        return existing.promise
    }

    const operation: ActivePull = {
        controller: new AbortController(),
        promise: Promise.resolve(),
        listeners: new Set([onProgress]),
    }
    pulls.set(key, operation)
    const report = (progress: OllamaPullProgress) => {
        operation.lastProgress = progress
        for (const listener of operation.listeners) listener(progress)
    }
    operation.promise = (async () => {
        await ensureServer(baseUrl)
        const response = await fetch(`${baseUrl}/api/pull`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model: name, stream: true }),
            signal: operation.controller.signal,
        })
        if (!response.ok || !response.body) {
            throw new Error(`Ollama download failed (${response.status}): ${await response.text()}`)
        }
        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let pending = ''
        let succeeded = false
        while (true) {
            const { value, done } = await reader.read()
            if (done) break
            pending += decoder.decode(value, { stream: true })
            const lines = pending.split('\n')
            pending = lines.pop() ?? ''
            for (const line of lines) {
                if (!line.trim()) continue
                const item = JSON.parse(line) as { status?: string; error?: string; total?: number; completed?: number }
                if (item.error) throw new Error(item.error)
                succeeded ||= item.status === 'success'
                report({ model: name, status: item.status ?? '', total: item.total ?? 0,
                    completed: item.completed ?? 0, done: item.status === 'success' })
            }
        }
        if (pending.trim()) {
            const item = JSON.parse(pending) as { status?: string; error?: string }
            if (item.error) throw new Error(item.error)
            succeeded ||= item.status === 'success'
            report({ model: name, status: item.status ?? '', completed: 0, total: 0, done: item.status === 'success' })
        }
        if (!succeeded) throw new Error('Ollama ended the download before confirming success.')
    })().finally(() => {
        if (pulls.get(key) === operation) pulls.delete(key)
    })
    return operation.promise
}

export function cancelOllamaPulls(): void {
    for (const operation of pulls.values()) operation.controller.abort()
    pulls.clear()
}
