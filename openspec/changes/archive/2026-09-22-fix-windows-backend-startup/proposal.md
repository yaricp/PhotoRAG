# Change: Fix Windows packaged backend startup

## Why

On Windows, the installer completes successfully and the setup wizard installs Python dependencies, but launching the installed app can hang until Electron reports that the backend did not respond. The app log only records a terse diagnostic like `python=... backendDir=... port=8000`, which looks like a command but is not directly runnable and does not include `run.py` or the required environment variables.

Manual testing of the installed files showed that `resources\backend\run.py` exists and the backend can start when run explicitly from the backend directory. The captured manual log also shows a slow Windows cold start: uvicorn begins before the app is ready, and `/api/system/status/` may not become available within the current 30 second Electron wait window.

Further setup testing showed that `pip` can spend a long time in the `Installing collected packages` phase after downloads complete. During that phase the wizard's determinate progress can sit near the end even though files continue to be installed, which makes the application look frozen.

Windows local model testing also showed that PyTorch can install successfully but fail at import time when the Microsoft Visual C++ Redistributable is missing. In that case `torch` reports `WinError 126` while loading `torch\lib\c10.dll`, and all local model setup paths that depend on PyTorch fail with a generic model-download error.

Runtime testing after setup also showed that the installed app can end up with two backend `run.py` processes and duplicate Huey workers. In that state only one backend can own the API port, while duplicate workers and observers make photo watcher behaviour difficult to reason about.

Watcher testing exposed a related stale-state problem: a watcher row can remain `active` in SQLite after the process that owned the watchdog observer has exited. Re-adding the same watcher path then returns the stale database row without starting a new observer, so the UI shows an active watcher while newly added photos are ignored.

Windows watcher testing against OneDrive-backed folders also showed that watchdog can emit `created` events before Explorer or OneDrive releases the file. The observer then tries to hash the image immediately, receives `PermissionError: [Errno 13] Permission denied`, and drops the photo without moving it or creating a database record.

## What Changes

- Make the Windows packaged backend launch easier to diagnose by logging a copy-pasteable `cmd.exe` reproduction block, including `cd /d`, `set APP_DATA_DIR`, `set API_PORT`, `set QUEUE_DB_DIR`, `set HUGGINGFACE_HUB_CACHE`, and `python.exe run.py`.
- Use `python.exe` for the packaged Windows backend process with `windowsHide: true` so stdout/stderr can be captured in `photorag.log`; keep non-Windows behaviour unchanged.
- Increase the packaged Windows backend readiness wait budget to cover slow cold starts observed on Windows while keeping the existing shorter wait for dev/macOS/Linux.
- Exclude local backend test artifacts from packaged resources so CI-generated files are not bundled into the Windows installer.
- Build Windows x64 and ARM64 installers separately so each installer bundles a Python runtime matching its Electron architecture.
- Validate persisted setup state before backend startup and rerun the Setup Wizard when reinstall leaves a missing or incompatible venv Python.
- Refresh the stable Python runtime copy and recreate the venv whenever the Setup Wizard installs dependencies.
- Install Python requirements through `python -m pip` from the venv, matching the manual Windows command that successfully advanced dependency installation.
- Keep the dependency installation step visibly active during long package installation phases across desktop platforms, even when a numeric percent cannot advance accurately.
- Detect and explain missing Microsoft Visual C++ Redistributable failures before local model setup reports a generic Python process failure.
- Make backend startup idempotent inside the Electron main process and guarded by a packaged Windows runtime lock so concurrent or repeated startup requests reuse the same backend process instead of spawning duplicate `run.py` processes and duplicate workers.
- Treat watcher activity as process-local state: restart an observer when a saved watcher is marked active in the database but is not running in the current backend process, and allow stale watcher records to be deleted safely.
- Wait for newly-created watcher files to become readable and size-stable before hashing and moving them, so copy/sync locks do not drop incoming photos.

## Non-goals

- Does not change the NSIS install location, per-user install model, or bundled backend layout.
- Does not change macOS startup behaviour.
- Does not try to compute exact per-package install percentages from `pip`; the goal is clear activity feedback rather than precise package-level progress.

## Impact

- Affected specs: `desktop-runtime`
- Affected files: `frontend/electron/main/backend.ts`, `frontend/electron/main/index.ts`, `frontend/electron/main/ipc.ts`, `frontend/electron/main/__tests__/backend.test.ts`, `frontend/electron/main/__tests__/ipc-install-deps.test.ts`, `frontend/electron/main/__tests__/ipc-pip-args.test.ts`, `frontend/electron/main/__tests__/package-config.test.ts`, `frontend/src/pages/SetupWizard/StepInstallDeps.tsx`, `frontend/package.json`
- Verification: targeted frontend tests for backend startup; full local CI where available; Windows installer build and packaged artifact sanity check.
