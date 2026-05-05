import '@testing-library/jest-dom'
import { beforeAll, afterAll, afterEach } from 'vitest'
import { server } from './server'

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

// Silence React Router v6 future flag warnings
const originalWarn = console.warn
beforeAll(() => {
    console.warn = (...args) => {
        if (typeof args[0] === 'string' && args[0].includes('React Router Future Flag')) return
        originalWarn(...args)
    }
})
afterAll(() => { console.warn = originalWarn })