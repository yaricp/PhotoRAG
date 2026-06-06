/**
 * notarize.js — Stub for electron-builder afterSign hook.
 *
 * TODO: Implement notarization when an Apple Developer account is available:
 *   1. Enroll in the Apple Developer Program.
 *   2. Generate a Developer ID Application certificate.
 *   3. Install @electron/notarize: npm install --save-dev @electron/notarize
 *   4. Set env vars: APPLE_ID, APPLE_APP_SPECIFIC_PASSWORD, APPLE_TEAM_ID
 *   5. Set mac.hardenedRuntime: true in electron-builder config.
 *   6. Replace this stub with:
 *
 *   const { notarize } = require('@electron/notarize')
 *   module.exports = async ({ appOutDir, packager }) => {
 *     if (packager.platform.name !== 'mac') return
 *     const appName = packager.appInfo.productName
 *     await notarize({
 *       tool: 'notarytool',
 *       appPath: `${appOutDir}/${appName}.app`,
 *       appleId: process.env.APPLE_ID,
 *       appleIdPassword: process.env.APPLE_APP_SPECIFIC_PASSWORD,
 *       teamId: process.env.APPLE_TEAM_ID,
 *     })
 *   }
 */
module.exports = async () => {
    // Notarization not yet configured — skip.
}
