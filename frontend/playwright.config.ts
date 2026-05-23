import { defineConfig } from '@playwright/test'

export default defineConfig({
    testDir: 'tests/e2e',
    timeout: 30_000,
    use: {
        baseURL: process.env.VITE_DEV_URL || 'http://localhost:5173',
        headless: true,
    },
    webServer: process.env.CI
        ? undefined
        : {
              command: 'npm run dev -- --port 5173',
              url: 'http://localhost:5173',
              reuseExistingServer: true,
              timeout: 30_000,
          },
})
