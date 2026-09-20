# Auto-updates for installed desktop app

## Decision

Implement auto-updates in stages. For the next practical implementation, PhotoRAG should use:

**Update checker + full installer download + manual confirmation before installation.**

Do not start with binary patches/delta updates. Do not try to replace the running application in place.

## Why this is the preferred first step

PhotoRAG bundles an Electron shell, frontend assets, backend Python code, a managed Python runtime, a user venv, local queues, SQLite data, thumbnail cache, and optional local model caches. Updating all of that while the app is running would be fragile: old frontend code could talk to new backend code, backend workers could keep old modules loaded, and Windows can lock executable files during replacement.

A full installer is larger, but it is much safer and easier to support across Windows, macOS, and Linux while the app is still stabilizing.

## User-facing behavior for the first implementation

- The installed app checks for newer releases periodically, for example on startup and then at most once per day.
- If a newer version exists, the app shows a non-blocking update banner/dialog.
- The dialog shows the new version, short release notes, and installer size if available.
- The user can choose:
  - download and install;
  - remind later;
  - open the release page;
  - disable automatic update checks in settings.
- If photo processing is currently active, the app warns the user and suggests installing after processing finishes.
- The app should not interrupt active processing without explicit confirmation.

## Installation flow

1. Fetch release metadata from GitHub Releases or a static JSON endpoint.
2. Compare the published version with the current app version.
3. Select the correct artifact for the current platform and architecture.
4. Download the full installer/package.
5. Verify the downloaded file using SHA256, and later code signing/signature validation where available.
6. Ask the user to confirm installation.
7. Stop PhotoRAG backend processes and workers cleanly.
8. Launch the installer/package.
9. Quit the current app.
10. The newly installed app starts and reuses existing user data.

## Release metadata shape

The release metadata should include enough information for the app to decide whether an update is available and which artifact to download.

Example:

```json
{
  "version": "0.1.4",
  "published_at": "2026-09-20T00:00:00Z",
  "notes": "Fixed Windows watcher, template tags, thumbnails, and pipeline retry.",
  "downloads": {
    "win-x64": {
      "url": "https://example.com/PhotoRAG-Setup-0.1.4-x64.exe",
      "sha256": "..."
    },
    "mac-universal": {
      "url": "https://example.com/PhotoRAG-0.1.4-universal.dmg",
      "sha256": "..."
    },
    "linux-x64": {
      "url": "https://example.com/PhotoRAG-0.1.4-x64.AppImage",
      "sha256": "..."
    }
  }
}
```

## Platform notes

### Windows

Use the NSIS installer as the update artifact. The app can download `PhotoRAG-Setup-<version>-x64.exe`, verify it, ask the user, stop backend processes, start the installer, and quit. This avoids replacing locked files while PhotoRAG is running.

### macOS

Use a signed/notarized DMG or a future auto-update mechanism once signing is stable. A smooth in-app update flow on macOS depends heavily on correct signing and notarization.

### Linux

Use AppImage as the first update artifact. Initially, support update checks and download/open behavior. True AppImage delta updates can be evaluated later.

## Deferred options

### True in-app auto-updater

Electron/electron-builder update tooling can be evaluated later. It may be useful once code signing, release hosting, and installer behavior are stable on all target platforms.

### Delta or patch updates

Delta updates should be deferred. They add complexity around integrity, rollback, platform differences, Python runtime changes, backend dependency changes, and model/cache compatibility. Full installers are acceptable for the first stable update mechanism.

### Hot-swapping components without restart

Only small data-like resources should be considered for live updates, such as prompts, release metadata, or optional vocabulary files. Application code, backend code, Python runtime, and dependencies should update through a full installer and app restart.

## Acceptance criteria for the future implementation

- The app can detect a newer published version.
- The app shows a clear update notification with version and release notes.
- The user stays in control of downloading and installing.
- The app downloads the correct artifact for platform and architecture.
- The app verifies SHA256 before offering installation.
- The app preserves existing user data under the user data directory.
- The app stops backend processes before running an installer.
- Update checks can be disabled in settings.
- Failed downloads or failed verification leave the current app untouched and show a useful error.
