# Auto-updates for installed desktop app

## Goal

PhotoRAG should be able to check whether a newer version is available after it has already been installed on a user's machine, then clearly offer the user an update path from inside the app.

## User-facing behavior to design

- The installed app periodically checks for a newer release.
- If a newer version is available, the app shows a clear, non-blocking notification with the version number and release notes summary.
- The user can choose to install the update now, postpone it, or open the release/download page.
- The app explains whether the update is a full installer download or a smaller patch/delta update.
- Updates must not interrupt active photo processing without warning.
- If an update fails, the current installed version should keep working and the user should get a useful error message.

## Platforms to consider

- Windows NSIS installer: evaluate whether we can support in-app update installation or should download/run a new installer.
- macOS DMG/app bundle: signing/notarization will matter for a smooth update flow.
- Linux AppImage: likely needs a separate strategy from Windows/macOS; document whether we support update checks only or AppImage delta updates.

## Technical questions

- Where should release metadata live: GitHub Releases, a static JSON endpoint, or both?
- Should we use Electron/electron-builder auto-update tooling, or keep a custom update checker that opens the latest release page?
- Do we need patch/delta updates immediately, or is a full installer download acceptable for the first version?
- How do we verify installer authenticity: checksums, signatures, code signing, or GitHub release provenance?
- How often should the app check for updates, and how should the user disable or defer checks?
- How should updates interact with first-run setup, local Python runtime, venv, cached models, user DB, and existing settings?

## Acceptance criteria for a future OpenSpec change

- A spec defines cross-platform update-check behavior and platform-specific installation behavior.
- The app can detect a newer published version and present it to the user.
- The user remains in control of installing updates.
- Existing app data under the user data directory is preserved.
- The update flow has tests or documented manual verification for Windows, macOS, and Linux.

## Rough implementation estimate

### Option 1: update checker only

The app checks GitHub Releases or a static release metadata JSON, detects that a newer version exists, and shows a non-blocking prompt with a link to download the installer manually.

Estimated effort:

- Time: 1–2 working days.
- Token budget: 40k–80k.
- Risk: low.
- Recommended as the first implementation step.

Expected scope:

- Read the current app version from the packaged app.
- Fetch latest release metadata.
- Compare semantic versions.
- Show a banner/dialog when an update is available.
- Add a user setting for automatic update checks.
- Add tests and documentation/OpenSpec coverage.

### Option 2: full in-app updater

The app downloads an update, verifies it, and offers to install/restart from inside the app. Platform behavior differs across Windows, macOS, and Linux.

Estimated effort:

- Time: 5–10 working days if there are no major platform surprises.
- Token budget: 150k–300k.
- Risk: medium/high.
- Better to defer until installers are stable.

Main complications:

- Windows NSIS updates while the Electron app is running.
- macOS signing/notarization requirements for a smooth user experience.
- Linux AppImage needs a separate update strategy.
- Decision between full installer download and delta/patch updates.
- Integrity verification via checksums, signatures, or release provenance.
- Preservation of user data, venv, models, database, and settings.
- Avoid interrupting active photo processing.

Recommendation: implement Option 1 first, then consider adding in-app installer download, and only after that evaluate true delta updates.
