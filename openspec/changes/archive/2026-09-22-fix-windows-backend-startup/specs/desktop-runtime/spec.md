# Spec delta: desktop-runtime

## ADDED Requirements

### Requirement: Packaged Windows app must wait for backend cold start

The packaged Windows Electron app SHALL allow enough time for the Python backend to complete a slow cold start before reporting startup failure.

#### Scenario: Slow Windows backend startup

- **WHEN** the installed Windows app launches after setup is complete
- **AND** the Python backend process starts successfully but `/api/system/status/` is not ready within 30 seconds
- **THEN** Electron continues polling for readiness using the packaged Windows startup budget instead of immediately showing a backend failure dialog

### Requirement: Packaged Windows backend launch must be diagnosable

The packaged Windows Electron app SHALL log the exact backend cwd, executable, arguments, and required environment variables in a form a user or developer can reproduce in `cmd.exe`.

#### Scenario: User debugs installed Windows backend

- **WHEN** the installed Windows app attempts to start the backend
- **THEN** `photorag.log` contains a copy-pasteable command sequence using `cd /d`, `set APP_DATA_DIR`, `set API_PORT`, `set QUEUE_DB_DIR`, `set HUGGINGFACE_HUB_CACHE`, and `python.exe run.py`

### Requirement: Windows installers must bundle the matching Python runtime architecture

Windows Electron installers SHALL be built one architecture at a time so the packaged Python runtime matches the Electron app architecture.

#### Scenario: Building the Windows x64 installer

- **WHEN** the Windows x64 installer build runs
- **THEN** the build packages the x64 Electron app with the x64 Python runtime
- **AND** it does not also emit ARM64 app resources using the x64 Python runtime

### Requirement: Packaged app must recover from stale setup state

The packaged Electron app SHALL validate the setup marker, venv Python executable, Windows executable format, and backend entrypoint before treating setup as complete.

#### Scenario: Reinstall leaves stale app data

- **WHEN** the app launches after reinstall
- **AND** the persisted setup marker exists
- **BUT** the persisted venv Python executable is missing or incompatible with the current Windows app architecture
- **THEN** the app opens the Setup Wizard instead of attempting to spawn the invalid backend Python executable

#### Scenario: User reruns dependency setup

- **WHEN** the Setup Wizard installs Python dependencies in a packaged Windows or Linux app
- **THEN** it refreshes the stable Python runtime copy in app data
- **AND** it recreates the venv before installing requirements
- **AND** it installs requirements through the venv Python module invocation `python -m pip`

#### Scenario: Dependency setup is invoked twice

- **WHEN** dependency setup is already running
- **AND** the renderer invokes dependency setup again before the first run finishes
- **THEN** the app reuses the running setup operation
- **AND** it does not launch a second `pip install` process for the same venv

### Requirement: Packaged Windows app must clean stale backend workers

The packaged Windows Electron app SHALL clean stale PhotoRAG backend runtime processes from the app venv before starting a new backend session.

#### Scenario: Previous backend workers remain after an abnormal exit

- **WHEN** the packaged Windows app starts
- **AND** stale `run.py` or `huey.bin.huey_consumer` Python processes from the PhotoRAG app venv still exist
- **THEN** the app terminates those stale backend runtime processes before spawning the new backend
- **AND** it does not target unrelated Python processes or `pip install` processes

### Requirement: Desktop backend startup must be idempotent

The Electron main process SHALL reuse an in-flight or already-running backend startup instead of spawning duplicate Python backend processes.

#### Scenario: Startup is requested twice

- **WHEN** the app is already starting or has started the Python backend
- **AND** another main-process path requests backend startup
- **THEN** the app returns the same backend port
- **AND** it does not spawn a second `run.py` process
- **AND** it does not create duplicate Huey worker processes

#### Scenario: Packaged Windows runtime lock already exists

- **WHEN** a packaged Windows app process attempts to start the backend
- **AND** the PhotoRAG backend runtime lock already exists
- **AND** the recorded backend port responds to the readiness endpoint
- **THEN** the app reuses the recorded backend port
- **AND** it does not spawn a second `run.py` process
- **AND** it does not remove the lock owned by the running backend process

### Requirement: Saved watchers must recover from stale active state

The backend SHALL treat a watcher's active observer as process-local state and SHALL not rely only on the persisted database status when deciding whether a watcher is running.

#### Scenario: Active watcher row has no running observer

- **WHEN** a watcher row already exists in the database with `status` set to `active`
- **AND** the current backend process has no running observer for that watcher
- **AND** the watcher is started again for the same path
- **THEN** the backend starts a new watchdog observer for that path
- **AND** it records the watcher as active for the current backend process

#### Scenario: Stale active watcher is deleted

- **WHEN** a watcher row exists in the database
- **AND** the current backend process has no running observer for that watcher
- **AND** the user deletes the watcher
- **THEN** the backend deletes the database row without raising an in-memory observer lookup error

### Requirement: Watcher must tolerate temporarily locked new files

The backend watcher SHALL wait for a newly-created image file to become readable and size-stable before hashing, moving, or registering it.

#### Scenario: File is still locked after creation event

- **WHEN** a watched folder emits a new image-file creation event
- **AND** the file is temporarily unreadable because it is still being copied or synchronized by the operating system
- **THEN** the watcher retries readiness checks instead of immediately dropping the file
- **AND** once the file becomes readable and its size is stable, the watcher hashes, moves, registers, and submits the photo to the pipeline

#### Scenario: File remains unavailable

- **WHEN** a watched folder emits a new image-file creation event
- **AND** the file remains unreadable through the readiness retry budget
- **THEN** the watcher logs that the file was not ready
- **AND** it does not create a partial photo record

### Requirement: Packaged desktop navigation must work from file URLs

The packaged Electron renderer SHALL support sidebar navigation when loaded from the packaged `file://` entrypoint.

#### Scenario: User clicks sidebar links in the packaged app

- **WHEN** the packaged renderer is loaded from `file://`
- **AND** the user clicks a sidebar navigation item
- **THEN** the displayed page changes to the selected route without requiring a server-side history fallback

### Requirement: Dependency installation must show ongoing activity

The Setup Wizard SHALL keep dependency-install progress visibly active on all desktop platforms while Python package installation is still running, including long `pip install` phases where the numeric percent cannot advance accurately.

#### Scenario: Pip installs packages after downloads complete

- **WHEN** the Setup Wizard is installing Python dependencies
- **AND** `pip` has finished downloading packages and is installing collected packages
- **AND** the numeric progress value does not change for an extended period
- **THEN** the UI continues to show visible activity
- **AND** it displays the current installation phase or recent package/activity text
- **AND** it does not appear frozen at a near-complete determinate progress state

#### Scenario: Pip emits output without a percent change

- **WHEN** the dependency installer receives new output from `pip`
- **AND** the calculated percent remains the same
- **THEN** the Setup Wizard updates the visible activity details so the user can tell work is still happening

### Requirement: Windows local model setup must report missing VC++ runtime

The Setup Wizard SHALL detect the Windows PyTorch DLL-load failure caused by a missing Microsoft Visual C++ Redistributable and report an actionable recovery message instead of only reporting a generic Python process exit.

#### Scenario: PyTorch cannot load c10.dll on Windows

- **WHEN** the user selects a local model setup path on Windows
- **AND** Python dependencies are installed
- **BUT** importing `torch` fails with `WinError 126` or a missing `torch\lib\c10.dll` dependency
- **THEN** the Setup Wizard reports that Microsoft Visual C++ Redistributable x64 is required
- **AND** it includes the download URL `https://aka.ms/vs/17/release/vc_redist.x64.exe`
- **AND** the app log contains the same diagnostic in the model download output tail
