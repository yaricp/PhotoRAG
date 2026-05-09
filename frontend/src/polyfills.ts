// Polyfill for crypto.getRandomValues in browser environments
if (!globalThis.crypto) {
    globalThis.crypto = {} as any
}

if (!globalThis.crypto.getRandomValues) {
    globalThis.crypto.getRandomValues = function (arr: Uint8Array | Uint16Array | Uint32Array) {
        for (let i = 0; i < arr.length; i++) {
            arr[i] = Math.floor(Math.random() * 256)
        }
        return arr
    }
}

if (!globalThis.crypto.randomUUID) {
    globalThis.crypto.randomUUID = function () {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
            const r = (Math.random() * 16) | 0
            const v = c === 'x' ? r : (r & 0x3) | 0x8
            return v.toString(16)
        })
    }
}
