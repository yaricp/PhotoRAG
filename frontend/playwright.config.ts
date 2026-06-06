import { defineConfig } from '@playwright/test'

export default defineConfig({
    testDir: 'tests/e2e',
    timeout: 30_000,
    use: {
        baseURL: process.env.VITE_DEV_URL || 'http://localhost:5173',
        headless: true,
    },
    webServer: {
        command: 'npm run dev -- --port 5173',
        url: 'http://localhost:5173',
        reuseExistingServer: !process.env.CI,
        timeout: 60_000,
    },
})
