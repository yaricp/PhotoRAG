// Polyfill the Fetch API for Node 16, which msw needs at module load time.
// This file must be listed BEFORE setup.ts in vitest setupFiles.
if (typeof globalThis.Request === 'undefined') {
    class _Request {
        url: string; method: string; headers: any; body: any
        mode: string; credentials: string; cache: string
        redirect: string; referrer: string

        constructor(input: string | _Request, init: any = {}) {
            this.url = typeof input === 'string' ? input : input.url
            this.method = (init.method ?? 'GET').toUpperCase()
            this.headers = init.headers ?? {}
            this.body = init.body ?? null
            this.mode = init.mode ?? 'cors'
            this.credentials = init.credentials ?? 'same-origin'
            this.cache = init.cache ?? 'default'
            this.redirect = init.redirect ?? 'follow'
            this.referrer = init.referrer ?? ''
        }

        clone() { return new _Request(this.url, this) }
        async text() { return this.body != null ? String(this.body) : '' }
        async json() { return JSON.parse(await this.text()) }
        async arrayBuffer() { return new ArrayBuffer(0) }
        async blob() { return new Blob([]) }
        async formData() { return new FormData() }
    }

    class _Response {
        status: number; statusText: string; headers: any; body: any; ok: boolean; type: string

        constructor(body?: any, init: any = {}) {
            this.status = init.status ?? 200
            this.statusText = init.statusText ?? ''
            this.headers = init.headers ?? {}
            this.body = body ?? null
            this.ok = this.status >= 200 && this.status < 300
            this.type = 'basic'
        }

        clone() { return new _Response(this.body, { status: this.status, headers: this.headers }) }
        async text() { return this.body != null ? String(this.body) : '' }
        async json() { return JSON.parse(await this.text()) }
        async arrayBuffer() { return new ArrayBuffer(0) }
        async blob() { return new Blob([]) }
        async formData() { return new FormData() }
    }

    globalThis.Request = _Request as any
    globalThis.Response = _Response as any

    if (typeof globalThis.Headers === 'undefined') {
        globalThis.Headers = class Headers {
            private _map: Record<string, string> = {}
            constructor(init?: any) {
                if (init && typeof init === 'object') {
                    Object.entries(init).forEach(([k, v]) => { this._map[k.toLowerCase()] = String(v) })
                }
            }
            get(name: string) { return this._map[name.toLowerCase()] ?? null }
            set(name: string, value: string) { this._map[name.toLowerCase()] = value }
            has(name: string) { return name.toLowerCase() in this._map }
            delete(name: string) { delete this._map[name.toLowerCase()] }
            forEach(cb: (v: string, k: string) => void) { Object.entries(this._map).forEach(([k, v]) => cb(v, k)) }
        } as any
    }

    if (typeof globalThis.fetch === 'undefined') {
        globalThis.fetch = (() => Promise.resolve(new globalThis.Response())) as any
    }
}
