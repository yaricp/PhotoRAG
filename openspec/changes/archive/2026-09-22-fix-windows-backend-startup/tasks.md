# Tasks: fix-windows-backend-startup

## 1. Specify expected Windows startup behaviour
- [x] 1.1 Add an OpenSpec delta for packaged Windows backend startup diagnostics and readiness timeout

## 2. Implement startup fix
- [x] 2.1 Use `python.exe` for packaged Windows backend launch while hiding the console window
- [x] 2.2 Log a copy-pasteable Windows reproduction command block with the same cwd and env Electron uses
- [x] 2.3 Give packaged Windows a longer backend readiness timeout
- [x] 2.4 Exclude local backend test artifacts from packaged Windows resources
- [x] 2.5 Build Windows x64 and ARM64 installers separately so each bundles a matching Python runtime
- [x] 2.6 Validate persisted setup state before backend startup and reopen the Setup Wizard for missing or incompatible venv Python
- [x] 2.7 Refresh stable Python and recreate the venv when dependency setup is rerun
- [x] 2.8 Install requirements through `python -m pip` from the venv during setup
- [x] 2.9 Prevent concurrent dependency setup runs from launching multiple `pip install` processes
- [x] 2.10 Enforce a single Electron app instance so a second launch cannot start a second backend
- [x] 2.11 Clean stale packaged Windows backend and Huey worker processes from the app venv on startup/shutdown
- [x] 2.12 Use hash routing for the packaged renderer so sidebar navigation works from `file://`
- [x] 2.13 Keep dependency-install UI visibly alive while `pip` is installing packages after downloads complete
- [x] 2.14 Surface the current installation phase and recent package/activity details for all desktop platforms
- [x] 2.15 Avoid showing a stalled near-complete determinate bar during long package install phases
- [x] 2.16 Detect missing Microsoft Visual C++ Redistributable before Windows local model setup imports PyTorch-backed installers
- [x] 2.17 Surface an actionable Windows VC++ Redistributable message instead of a generic model-download process failure
- [x] 2.18 Make backend startup idempotent so repeated setup/main startup calls cannot spawn duplicate `run.py` processes
- [x] 2.18.1 Guard packaged Windows backend ownership with a runtime lock and reusable port file
- [x] 2.19 Restart watchers whose persisted DB status is active but whose observer is not running in the current backend process
- [x] 2.20 Allow deletion of stale watcher records without an in-memory observer
- [x] 2.21 Wait for newly-created watcher files to become readable and size-stable before hashing or moving them

## 3. Verify
- [x] 3.1 Add/update frontend unit tests for Windows packaged startup
- [x] 3.2 Run targeted frontend tests
- [x] 3.3 Run full local CI where available
- [x] 3.4 Build Windows installer locally
- [x] 3.5 Verify packaged Windows artifacts include the startup fix and exclude local test files
- [x] 3.6 Add/update tests for duplicate setup guards, stale process cleanup, and sidebar navigation
- [x] 3.7 Add frontend tests for dependency-install activity feedback when percent does not change
- [x] 3.8 Verify the setup wizard communicates ongoing `pip install` work on Windows, macOS, and Linux
- [x] 3.9 Add/update tests for Windows model setup VC++ Redistributable diagnostics
- [x] 3.10 Add/update tests for repeated backend startup reusing the in-flight or already-running process
- [x] 3.10.1 Add/update tests for packaged Windows runtime lock reuse
- [x] 3.11 Add backend watcher-service tests for stale active watcher recovery and deletion
- [x] 3.12 Add backend observer tests for file readiness retries after copy/sync locks
