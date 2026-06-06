// Polyfill missing browser globals for Node 16 (jsdom 24 doesn't include them).
// This file must be listed BEFORE setup.ts in vitest setupFiles.

// Web Streams (ReadableStream, WritableStream, TransformStream) — required by msw 2.x.
// Node 16 has them in 'stream/web' but doesn't expose them on globalThis.
if (typeof globalThis.ReadableStream === 'undefined') {
    try {
        // eslint-disable-next-line @typescript-eslint/no-require-imports
        const sw = require('stream/web') as Record<string, unknown>
        for (const key of Object.keys(sw)) {
            if (typeof (globalThis as Record<string, unknown>)[key] === 'undefined') {
                (globalThis as Record<string, unknown>)[key] = sw[key]
            }
        }
    } catch {
        // Node < 16.5 — streams/web not available, MSW will be skipped
    }
}

// BroadcastChannel is required by msw 2.x at module-load time.
if (typeof globalThis.BroadcastChannel === 'undefined') {
    class _BroadcastChannel extends EventTarget {
        name: string
        onmessage: ((ev: MessageEvent) => void) | null = null
        onmessageerror: ((ev: MessageEvent) => void) | null = null
        constructor(name: string) { super(); this.name = name }
        postMessage(msg: unknown) {
            this.dispatchEvent(new MessageEvent('message', { data: msg }))
        }
        close() {}
    }
    ;(globalThis as any).BroadcastChannel = _BroadcastChannel
}

if (typeof globalThis.Request === 'undefined') {
    // Headers must be defined first so Request/Response constructors can use it.
    class _Headers {
        private _map: Record<string, string> = {}
        constructor(init?: any) {
            if (init == null) return
            if (init instanceof _Headers) {
                this._map = { ...init._map }
            } else if (typeof init === 'object') {
                for (const [k, v] of Object.entries(init as Record<string, unknown>)) {
                    this._map[k.toLowerCase()] = String(v)
                }
            }
        }
        get(name: string) { return this._map[name.toLowerCase()] ?? null }
        set(name: string, value: string) { this._map[name.toLowerCase()] = value }
        has(name: string) { return name.toLowerCase() in this._map }
        delete(name: string) { delete this._map[name.toLowerCase()] }
        forEach(cb: (v: string, k: string) => void) {
            Object.entries(this._map).forEach(([k, v]) => cb(v, k))
        }
        entries() { return Object.entries(this._map)[Symbol.iterator]() }
        keys() { return Object.keys(this._map)[Symbol.iterator]() }
        values() { return Object.values(this._map)[Symbol.iterator]() }
    }
    if (typeof globalThis.Headers === 'undefined') {
        globalThis.Headers = _Headers as any
    }

    const H = (globalThis.Headers ?? _Headers) as typeof _Headers

    class _Request {
        url: string; method: string; headers: InstanceType<typeof _Headers>; body: any
        mode: string; credentials: string; cache: string
        redirect: string; referrer: string; signal: AbortSignal

        constructor(input: string | _Request, init: any = {}) {
            this.url = typeof input === 'string' ? input : input.url
            this.method = (init.method ?? 'GET').toUpperCase()
            this.headers = init.headers instanceof H ? init.headers : new H(init.headers)
            this.body = init.body ?? null
            this.mode = init.mode ?? 'cors'
            this.credentials = init.credentials ?? 'same-origin'
            this.cache = init.cache ?? 'default'
            this.redirect = init.redirect ?? 'follow'
            this.referrer = init.referrer ?? ''
            this.signal = init.signal ?? new AbortController().signal
        }

        clone() { return new _Request(this.url, this) }
        async text() { return this.body != null ? String(this.body) : '' }
        async json() { return JSON.parse(await this.text()) }
        async arrayBuffer() { return new ArrayBuffer(0) }
        async blob() { return new Blob([]) }
        async formData() { return new FormData() }
    }

    class _Response {
        status: number; statusText: string; headers: InstanceType<typeof _Headers>
        body: any; ok: boolean; type: string; url: string

        constructor(body?: any, init: any = {}) {
            this.status = init.status ?? 200
            this.statusText = init.statusText ?? ''
            this.headers = init.headers instanceof H ? init.headers : new H(init.headers)
            this.body = body ?? null
            this.ok = this.status >= 200 && this.status < 300
            this.type = 'basic'
            this.url = init.url ?? ''
        }

        clone() {
            return new _Response(this.body, {
                status: this.status,
                statusText: this.statusText,
                headers: this.headers,
            })
        }
        async text() { return this.body != null ? String(this.body) : '' }
        async json() { return JSON.parse(await this.text()) }
        async arrayBuffer() { return new ArrayBuffer(0) }
        async blob() { return new Blob([]) }
        async formData() { return new FormData() }
    }

    globalThis.Request = _Request as any
    globalThis.Response = _Response as any

    if (typeof globalThis.fetch === 'undefined') {
        globalThis.fetch = (() => Promise.resolve(new globalThis.Response())) as any
    }
}
