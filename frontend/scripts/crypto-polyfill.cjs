// Polyfill crypto.getRandomValues for Vite CJS build (Node < 19 / vite 5.4.x bug)
const crypto = require('crypto')
if (!crypto.getRandomValues) {
    crypto.getRandomValues = (arr) => {
        const bytes = crypto.randomBytes(arr.byteLength)
        arr.set(new Uint8Array(bytes.buffer, bytes.byteOffset, bytes.byteLength))
        return arr
    }
}
