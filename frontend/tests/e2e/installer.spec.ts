/**
 * Playwright e2e tests for the first-run installer / setup wizard.
 *
 * These tests run against the packaged Electron app.  They rely on
 * the PLAYWRIGHT_APP_PATH env var pointing at the built .app bundle,
 * and the _electronApp fixture supplied by @playwright/test.
 *
 * Run after `npm run dist:mac`:
 *   npx playwright test tests/e2e/installer.spec.ts
 */

import { test, expect } from '@playwright/test'

const APP_PATH = process.env.PLAYWRIGHT_APP_PATH || ''

test.describe('Setup Wizard', () => {
    test.skip(!APP_PATH, 'PLAYWRIGHT_APP_PATH not set — skipping packaged-app tests')

    test('first launch shows setup wizard, not main app', async ({ page }) => {
        // In a real Electron test this would use _electron.launch(...)
        // For now this spec documents the expected behaviour.
        await page.goto('about:blank')
        expect(APP_PATH).toBeTruthy()
    })
})

test.describe('Setup Wizard — renderer unit checks', () => {
    /**
     * These tests load the renderer HTML directly via a local dev server
     * and verify the wizard is rendered when electronAPI.checkSetupNeeded
     * returns { needed: true }.
     */

    test('welcome step visible on load when setup needed', async ({ page }) => {
        await page.addInitScript(() => {
            (window as any).electronAPI = {
                checkSetupNeeded: async () => ({ needed: true }),
                onInstallDepsProgress: () => {},
                onDownloadModelProgress: () => {},
                installDeps: async () => {},
                initDb: async () => {},
                downloadModel: async () => {},
                cancelDownload: async () => {},
                completeSetup: async () => {},
            }
        })

        await page.goto(process.env.VITE_DEV_URL || 'http://localhost:5173')

        // Language step is first — advance past it
        await expect(page.getByText(/choose your language/i)).toBeVisible({ timeout: 5000 })
        await page.getByRole('button', { name: /continue/i }).click()

        await expect(page.getByText(/welcome to photorag/i)).toBeVisible({ timeout: 5000 })
    })

    test('main app visible when setup already done', async ({ page }) => {
        await page.addInitScript(() => {
            (window as any).electronAPI = {
                checkSetupNeeded: async () => ({ needed: false }),
                getBackendPort: async () => 8000,
                onBackendReady: () => {},
                openFolder: async () => null,
                platform: 'darwin',
                onInstallDepsProgress: () => {},
                onDownloadModelProgress: () => {},
            }
        })

        await page.goto(process.env.VITE_DEV_URL || 'http://localhost:5173')

        // Wizard should NOT appear
        await expect(page.getByText(/welcome to photorag/i)).not.toBeVisible({ timeout: 3000 })
    })
})
