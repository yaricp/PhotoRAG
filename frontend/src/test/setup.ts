import '@testing-library/jest-dom'
import { beforeAll, afterAll, afterEach } from 'vitest'
import '../i18n'

if (typeof window !== 'undefined' && !window.localStorage) {
    const store = new Map<string, string>()
    const localStorageMock: Storage = {
        get length() { return store.size },
        clear: () => store.clear(),
        getItem: (key) => store.get(key) ?? null,
        key: (index) => Array.from(store.keys())[index] ?? null,
        removeItem: (key) => { store.delete(key) },
        setItem: (key, value) => { store.set(key, String(value)) },
    }
    Object.defineProperty(window, 'localStorage', {
        configurable: true,
        value: localStorageMock,
    })
    Object.defineProperty(globalThis, 'localStorage', {
        configurable: true,
        value: localStorageMock,
    })
}

// msw 2.x requires Node ≥ 18 (BroadcastChannel, WritableStream, native fetch, etc.).
// On older runtimes, skip MSW server setup so pure unit tests can still run.
const canUseMsw = typeof globalThis.BroadcastChannel !== 'undefined'
    && typeof globalThis.ReadableStream !== 'undefined'

let server: { listen: (opts?: Record<string, unknown>) => void; resetHandlers: () => void; close: () => void } | null = null

if (canUseMsw) {
    beforeAll(async () => {
        const m = await import('./server')
        server = m.server
        server!.listen({ onUnhandledRequest: 'error' })
        window.HTMLElement.prototype.scrollIntoView = () => {}
    })
    afterEach(() => server?.resetHandlers())
    afterAll(() => server?.close())
}

// Silence React Router v6 future flag warnings
const originalWarn = console.warn
beforeAll(() => {
    console.warn = (...args) => {
        if (typeof args[0] === 'string' && args[0].includes('React Router Future Flag')) return
        originalWarn(...args)
    }
})
afterAll(() => { console.warn = originalWarn })
