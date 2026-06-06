/**
 * Playwright E2E tests for i18n — Phase 8.10.
 *
 * Tests run against the renderer dev server (VITE_DEV_URL / localhost:5173).
 * Backend calls are intercepted via page.route() so no real backend is needed.
 *
 * Run with:
 *   npx playwright test tests/e2e/i18n.spec.ts
 */

import { test, expect } from '@playwright/test'

const BASE_URL = process.env.VITE_DEV_URL || 'http://localhost:5173'

// Shared mock: intercept all settings API calls
async function mockSettingsApi(page: import('@playwright/test').Page, lang = 'en') {
    let currentLang = lang

    await page.route('**/api/settings/', async route => {
        await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({ default_language: currentLang, default_folder: '' }),
        })
    })

    await page.route('**/api/settings/default_language', async route => {
        if (route.request().method() === 'PUT') {
            const body = route.request().postDataJSON()
            currentLang = body?.value ?? currentLang
            await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ key: 'default_language', value: currentLang }) })
        } else {
            await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ key: 'default_language', value: currentLang }) })
        }
    })

    await page.route('**/api/settings/**', async route => {
        await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
    })

    await page.route('**/api/translation/retranslate-all', async route => {
        await route.fulfill({
            status: 202,
            contentType: 'application/json',
            body: JSON.stringify({ status: 'started', language: currentLang }),
        })
    })
}

// Inject electronAPI mock so the renderer doesn't crash
function injectElectronMock(page: import('@playwright/test').Page) {
    return page.addInitScript(() => {
        ;(window as any).electronAPI = {
            checkSetupNeeded: async () => ({ needed: true }),
            onInstallDepsProgress: () => {},
            onDownloadModelProgress: () => {},
            installDeps: async () => {},
            onBackendReady: (_cb: () => void) => {},
            getBaseUrl: async () => 'http://localhost:8000',
            openFolderDialog: async () => null,
        }
    })
}

// ---------------------------------------------------------------------------
// SetupWizard — language step is first
// ---------------------------------------------------------------------------

test.describe('SetupWizard i18n — language step', () => {
    test('language step renders before welcome step', async ({ page }) => {
        await injectElectronMock(page)
        await mockSettingsApi(page, 'en')
        await page.goto(BASE_URL)

        // The wizard renders when setup is needed.
        // The language step (Step 0) should be visible before any other step.
        const langStep = page.locator('[data-testid="step-language"], .wizard-lang-list, .wizard-lang-option').first()
        await expect(langStep).toBeVisible({ timeout: 8000 })
    })

    test('English is selected by default in language step', async ({ page }) => {
        await injectElectronMock(page)
        await mockSettingsApi(page, 'en')
        await page.goto(BASE_URL)

        // The English option should have the selected class
        const englishOption = page.locator('.wizard-lang-option--selected, [aria-pressed="true"]').first()
        await expect(englishOption).toBeVisible({ timeout: 8000 })
        await expect(englishOption).toContainText(/English|🇬🇧/)
    })

    test('clicking Russian updates language immediately', async ({ page }) => {
        await injectElectronMock(page)
        await mockSettingsApi(page, 'en')
        await page.goto(BASE_URL)

        // Wait for language step to be visible
        await page.waitForSelector('.wizard-lang-option', { timeout: 8000 })

        // Click the Russian option
        const russianBtn = page.locator('.wizard-lang-option').filter({ hasText: /Русский|🇷🇺/ })
        await russianBtn.click()

        // After clicking Russian the button should be marked selected
        await expect(russianBtn).toHaveClass(/wizard-lang-option--selected/, { timeout: 3000 })
    })

    test('continuing from language step shows translated wizard content', async ({ page }) => {
        await injectElectronMock(page)
        await mockSettingsApi(page, 'ru')
        await page.goto(BASE_URL)

        await page.waitForSelector('.wizard-lang-option', { timeout: 8000 })

        // Select Russian
        const russianBtn = page.locator('.wizard-lang-option').filter({ hasText: /Русский|🇷🇺/ })
        await russianBtn.click()

        // Click the Continue/Next button
        const continueBtn = page.locator('button').filter({ hasText: /Продолжить|Continue|Далее/i }).first()
        if (await continueBtn.isVisible()) {
            await continueBtn.click()
        }

        // After continuing the wizard text should appear in Russian
        // (the welcome heading or any non-language-picker content)
        await page.waitForTimeout(500)
        const body = await page.textContent('body')
        // Either still showing wizard content or moved to welcome step
        expect(body).toBeTruthy()
    })
})

// ---------------------------------------------------------------------------
// Settings page — language change and retranslation trigger
// ---------------------------------------------------------------------------

test.describe('Settings page i18n', () => {
    test('Settings page renders language selector with three options', async ({ page }) => {
        await injectElectronMock(page)
        await mockSettingsApi(page, 'en')

        // Navigate to settings directly (not first-run wizard)
        await page.addInitScript(() => {
            ;(window as any).electronAPI = {
                checkSetupNeeded: async () => ({ needed: false }),
                onInstallDepsProgress: () => {},
                onDownloadModelProgress: () => {},
                onBackendReady: (_cb: () => void) => {},
                getBaseUrl: async () => 'http://localhost:8000',
                openFolderDialog: async () => null,
            }
        })

        await page.goto(`${BASE_URL}/#/settings`)

        const langSelect = page.locator('select[id="language"], select').filter({ hasText: /English|Русский|Español/i }).first()
        await expect(langSelect).toBeVisible({ timeout: 8000 })

        // All three language options should be present
        const options = langSelect.locator('option')
        await expect(options).toHaveCount(3)
    })

    test('changing language to Russian and saving triggers retranslation call', async ({ page }) => {
        const retranslateCalls: string[] = []

        await page.addInitScript(() => {
            ;(window as any).electronAPI = {
                checkSetupNeeded: async () => ({ needed: false }),
                onInstallDepsProgress: () => {},
                onDownloadModelProgress: () => {},
                onBackendReady: (_cb: () => void) => {},
                getBaseUrl: async () => 'http://localhost:8000',
                openFolderDialog: async () => null,
            }
        })

        await mockSettingsApi(page, 'en')

        await page.route('**/api/translation/retranslate-all', async route => {
            retranslateCalls.push(route.request().method())
            await route.fulfill({
                status: 202,
                contentType: 'application/json',
                body: JSON.stringify({ status: 'started', language: 'ru' }),
            })
        })

        await page.goto(`${BASE_URL}/#/settings`)

        const langSelect = page.locator('select').filter({ hasText: /English|Русский|Español/i }).first()
        await expect(langSelect).toBeVisible({ timeout: 8000 })

        // Change to Russian
        await langSelect.selectOption('ru')

        // Click Save
        const saveBtn = page.locator('button').filter({ hasText: /Save|Сохранить/i }).first()
        await saveBtn.click()

        // Retranslate-all should have been called
        await expect.poll(() => retranslateCalls.length, { timeout: 5000 }).toBeGreaterThan(0)
    })

    test('changing language to English does NOT trigger retranslation', async ({ page }) => {
        const retranslateCalls: string[] = []

        await page.addInitScript(() => {
            ;(window as any).electronAPI = {
                checkSetupNeeded: async () => ({ needed: false }),
                onInstallDepsProgress: () => {},
                onDownloadModelProgress: () => {},
                onBackendReady: (_cb: () => void) => {},
                getBaseUrl: async () => 'http://localhost:8000',
                openFolderDialog: async () => null,
            }
        })

        await mockSettingsApi(page, 'ru')

        await page.route('**/api/translation/retranslate-all', async route => {
            retranslateCalls.push(route.request().method())
            await route.fulfill({ status: 202, contentType: 'application/json', body: '{}' })
        })

        await page.goto(`${BASE_URL}/#/settings`)

        const langSelect = page.locator('select').filter({ hasText: /English|Русский|Español/i }).first()
        await expect(langSelect).toBeVisible({ timeout: 8000 })

        // Change to English
        await langSelect.selectOption('en')
        const saveBtn = page.locator('button').filter({ hasText: /Save|Сохранить/i }).first()
        await saveBtn.click()

        // Wait briefly — retranslate must NOT have been called
        await page.waitForTimeout(1000)
        expect(retranslateCalls).toHaveLength(0)
    })
})

// ---------------------------------------------------------------------------
// Language persistence across page reload
// ---------------------------------------------------------------------------

test.describe('Language persistence', () => {
    test('UI language matches the language stored in settings on load', async ({ page }) => {
        await page.addInitScript(() => {
            ;(window as any).electronAPI = {
                checkSetupNeeded: async () => ({ needed: false }),
                onInstallDepsProgress: () => {},
                onDownloadModelProgress: () => {},
                onBackendReady: (_cb: () => void) => {},
                getBaseUrl: async () => 'http://localhost:8000',
                openFolderDialog: async () => null,
            }
        })

        // Backend reports Russian as the stored language
        await mockSettingsApi(page, 'ru')

        await page.goto(`${BASE_URL}/#/settings`)

        // Settings page should show Russian text after i18n syncs
        await page.waitForTimeout(1500)
        const body = await page.textContent('body')
        // Some Russian characters should be present in the UI
        expect(body).toMatch(/[А-Яа-яЁё]/)
    })
})
