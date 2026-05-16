# macOS Installer — Implementation Plan

**Photo Describer 2 · Target: macOS 13+ arm64/x86_64 universal**

---

## 1. Overview & Architecture

### What We Are Building

A polished, double-click `.dmg` that installs a self-contained macOS app. The user drags it to `/Applications`, opens it, walks through a one-time setup wizard, and the app runs entirely offline (with optional remote API fallback). No Homebrew, no Python, no pip — everything the app needs is inside the `.app` bundle or in `~/Library/Application Support/PhotoDescriber2/`.

### High-Level Architecture

```
PhotoDescriber2.app/
  Contents/
    MacOS/
      PhotoDescriber2                  ← Electron binary
    Resources/
      app.asar                         ← compiled React/Electron JS
      python/                          ← python-build-standalone 3.13 (arm64+x86_64)
        bin/python3
        lib/...
      backend/                         ← backend source tree (full copy of backend/)
        run.py
        src/
        requirements.txt
        pyproject.toml
        data/                          ← vocab CSV/txt (read-only reference data)

~/Library/Application Support/PhotoDescriber2/   ← APP_DATA_DIR (mutable)
  .env                                 ← user config (API keys, modes)
  db.sqlite3                           ← main photo database
  clip.sqlite3
  embedding.sqlite3
  folder_scan.sqlite3
  ocr.sqlite3
  translation.sqlite3
  vision.sqlite3
  task_results.db
  data/                                ← CLIP .npy caches (generated at setup)
    tags_features.npy
    categories_features.npy
  venv/                                ← pip venv (created at setup, uses bundled Python)

~/.cache/huggingface/                  ← ML model weights (downloaded at setup or lazily)
```

### Data Flow on First Launch

```
Electron starts
    │
    ├─ APP_DATA_DIR/venv/ exists?
    │       YES → startBackend() → splash → main app
    │       NO  → SetupWizard (React page)
    │
    │   Step 1: Welcome
    │   Step 2: Install deps   ← IPC: setup:install-deps
    │   Step 3: Init DB        ← IPC: setup:init-db
    │   Step 4: Model picker   ← user selects models
    │   Step 5: Download       ← IPC: setup:download-model (per model)
    │   Step 6: Done           ← IPC: setup:complete → startBackend()
    │
Backend process (python run.py)
    ├─ Reads APP_DATA_DIR from env
    ├─ Loads .env from APP_DATA_DIR/.env
    ├─ Opens all SQLite DBs from APP_DATA_DIR/
    ├─ Starts Huey workers (6 subprocesses)
    └─ Serves FastAPI on 127.0.0.1:<dynamic_port>
```

### User Decisions

| Decision | Choice |
|---|---|
| Target user | General public — polished, double-click experience |
| Python | Bundle **python-build-standalone 3.13** (arm64 + x86_64 universal) |
| Models | User **chooses** in setup wizard; lazy download on first use as fallback |
| Data location | `~/Library/Application Support/PhotoDescriber2/` |
| Backend lifecycle | Starts/stops with the Electron window (no LaunchAgent) |
| Code signing | Skip for now; documented as a future step |

---

## 2. Phase-by-Phase Breakdown

---

### Phase 1 — Data Directory Migration (Backend)

**Goal:** All mutable file paths resolve to `~/Library/Application Support/PhotoDescriber2/` on macOS. The backend works identically in dev and inside the `.app` bundle.

#### Files to Create/Modify

| File | Action |
|---|---|
| `backend/src/data_dir.py` | Create — path resolver + migration helper |
| `backend/src/config.py` | Modify — use APP_DATA_DIR for all paths |
| `backend/run.py` | Modify — call migration on startup |
| `backend/src/queues/*.py` (6 files) | Modify — QUEUE_DB_DIR env var |
| `backend/tests/test_data_dir.py` | Create — TDD first |

#### TDD: Write These Tests First

```python
# backend/tests/test_data_dir.py
test_resolves_macos_path()          # sys.platform='darwin' → ~/Library/Application Support/PhotoDescriber2/
test_resolves_linux_path()          # sys.platform='linux' → ~/.local/share/PhotoDescriber2/
test_env_override()                 # APP_DATA_DIR=/tmp/test → uses that verbatim
test_migration_copies_sqlite_files()  # shutil.copy2 called for each of 7 .sqlite3 + task_results.db
test_migration_skips_if_already_migrated()  # target exists → no copy
test_migration_copies_dotenv()      # .env is also migrated
test_migration_copies_data_npy_files()  # data/*.npy and data/*.hash are copied
```

#### Implementation Steps

1. **Create `backend/src/data_dir.py`**:
   - `resolve_app_data_dir() -> Path` — checks `APP_DATA_DIR` env var first; otherwise `~/Library/Application Support/PhotoDescriber2/` on darwin, `~/.local/share/PhotoDescriber2/` on linux. Creates the directory.
   - `migrate_legacy_data(project_root: Path, app_data_dir: Path) -> None` — idempotent copy of each legacy file. Before copying SQLite files, runs `PRAGMA wal_checkpoint(TRUNCATE)` to flush WAL. Also copies `*.sqlite3-wal` and `*.sqlite3-shm` if present.

2. **Modify `backend/src/config.py`** — import `resolve_app_data_dir`, compute `_APP_DATA_DIR` at module top, update all path defaults:
   - `DATABASE_NAME` → `_APP_DATA_DIR / "db.sqlite3"`
   - `TASK_RESULT_DB_PATH` → `_APP_DATA_DIR / "task_results.db"`
   - All CLIP `.npy`, `.csv`, `.txt`, `.hash` paths → `_APP_DATA_DIR / "data/" / filename`
   - Read-only vocab files (CSV/TXT) detect bundled mode via `sys.frozen` or `RESOURCES_PATH` env and read from `Resources/backend/data/` instead.

3. **Modify `backend/run.py`** — call `migrate_legacy_data(Path(__file__).parent, _APP_DATA_DIR)` at startup before anything else.

4. **Fix queue DB paths** — introduce `QUEUE_DB_DIR` env var. Each queue file: `_DB_DIR = os.environ.get('QUEUE_DB_DIR', os.path.join(os.getcwd(), '..'))`. Electron sets `QUEUE_DB_DIR = APP_DATA_DIR`.

5. **Fix `load_dotenv()`** — change to `load_dotenv(_APP_DATA_DIR / ".env", override=False)`.

#### Success Criteria

- All existing backend tests pass.
- `test_data_dir.py` all pass.
- Running in dev creates files in `~/Library/Application Support/PhotoDescriber2/` on macOS.
- Queue `.sqlite3` files appear in `APP_DATA_DIR/`, not in the project root.

---

### Phase 2 — Backend Lifecycle Management in Electron

**Goal:** Electron starts the bundled Python backend before showing the main window, shows a splash screen while waiting, kills the entire process tree on quit.

#### Files to Create/Modify

| File | Action |
|---|---|
| `frontend/electron/main/backend.ts` | Rewrite — real start/stop/wait implementation |
| `frontend/electron/main/index.ts` | Modify — integrate lifecycle, splash window |
| `frontend/electron/main/ipc.ts` | Modify — add setup channels, dynamic port |
| `frontend/electron/preload/index.ts` | Modify — expose new IPC channels |
| `frontend/src/types/electron.d.ts` | Modify — add new IPC types |
| `frontend/resources/splash.html` | Create — standalone splash (no React) |
| `frontend/src/App.tsx` | Modify — check setup needed on mount |
| `frontend/electron/main/__tests__/backend.test.ts` | Modify — add real tests |

#### TDD: Write These Tests First

```typescript
// frontend/electron/main/__tests__/backend.test.ts
test_findFreePort_returns_number()
test_startBackend_dev_mode_uses_system_python()       // app.isPackaged=false → spawn 'python3' run.py
test_startBackend_packaged_uses_bundled_python()      // app.isPackaged=true → spawn Resources/python/bin/python3
test_startBackend_passes_APP_DATA_DIR_env()           // env.APP_DATA_DIR = app.getPath('userData')
test_startBackend_passes_port_env()                   // env.API_PORT = dynamic port
test_stopBackend_kills_process_group()                // process.kill(-pid, 'SIGTERM') called
test_waitForBackend_resolves_when_200()               // fetch returns ok on 2nd try → resolves
test_waitForBackend_rejects_after_max_retries()       // fetch always throws → rejects
```

#### Implementation Steps

1. **Rewrite `backend.ts`**:
   - `locatePython()` — `Resources/python/bin/python3` (packaged) or `'python3'` (dev).
   - `locateBackend()` — `Resources/backend` (packaged) or `../../../backend` (dev).
   - `getAppDataDir()` — `app.getPath('userData')`.
   - `startBackend()` — find free port, spawn with `detached: true`, env `{ APP_DATA_DIR, API_PORT, QUEUE_DB_DIR, HUGGINGFACE_HUB_CACHE }`, stream stdout/stderr to console.
   - `stopBackend()` — `process.kill(-pid, 'SIGTERM')`, SIGKILL after 5 s if still alive.
   - `waitForBackend(port, maxRetries=60)` — polls `GET /api/system/status/` every 500 ms.
   - Export `getBackendPort(): number | null`.

2. **Modify `index.ts`**:
   - `app.setName('PhotoDescriber2')` before `app.whenReady()` (forces correct userData path in dev).
   - Show `splash.html` in a frameless 400×200 `BrowserWindow` immediately.
   - Call `startBackend()` → `waitForBackend()` → close splash → open main window.
   - `app.on('will-quit')` → `stopBackend()`.

3. **Create `splash.html`** — plain HTML with inline CSS: spinner + "Starting Photo Describer…".

4. **Modify `ipc.ts`** — add `setup:check-needed` handler: `fs.existsSync(path.join(appDataDir, 'venv'))`.

5. **Modify `App.tsx`** — on mount call `checkSetupNeeded()`; render `<SetupWizard />` or `<AppRoutes />`.

#### Success Criteria

- Jest tests all pass.
- In packaged mode, `startBackend()` uses the bundled Python.
- Port is dynamic; both backend and frontend use it.
- `stopBackend()` kills the entire process tree including Huey workers.
- Splash screen appears, disappears when backend is ready (< 3 s on warm start).

---

### Phase 3 — Bundle Python + Backend in the Electron Build

**Goal:** `npm run dist:mac` produces a self-contained `.dmg` with Python and the backend inside.

#### Files to Create/Modify

| File | Action |
|---|---|
| `scripts/download-python.sh` | Create |
| `scripts/build-mac.sh` | Create |
| `scripts/test-bundle-structure.sh` | Create |
| `scripts/notarize.js` | Create — stub |
| `frontend/package.json` | Modify — electron-builder config + scripts |

#### TDD: Write These Tests First

```bash
# scripts/test-bundle-structure.sh — structural assertions on the built .app
assert_exists "PhotoDescriber2.app/Contents/Resources/python/bin/python3"
assert_executable "PhotoDescriber2.app/Contents/Resources/python/bin/python3"
assert_exists "PhotoDescriber2.app/Contents/Resources/backend/run.py"
assert_exists "PhotoDescriber2.app/Contents/Resources/backend/src/main.py"
assert_universal "PhotoDescriber2.app/Contents/Resources/python/bin/python3"  # lipo check
```

#### Implementation Steps

1. **`scripts/download-python.sh`**:
   - Download `cpython-3.13.X-aarch64-apple-darwin-install_only.tar.gz` and `cpython-3.13.X-x86_64-apple-darwin-install_only.tar.gz` from `github.com/astral-sh/python-build-standalone`.
   - Extract both; merge `python3` binaries with `lipo -create -output`.
   - Output to `frontend/resources/python/`.
   - Remove quarantine: `xattr -dr com.apple.quarantine frontend/resources/python/`.
   - Verify: `./python3 -m ensurepip --version`; fall back to `get-pip.py` if needed.
   - Skip if version hash matches (idempotent).

2. **`frontend/package.json` — electron-builder `"build"` section**:
   ```json
   {
     "appId": "com.photodescriber.app",
     "productName": "PhotoDescriber2",
     "mac": {
       "category": "public.app-category.photography",
       "target": [{ "target": "dmg", "arch": ["universal"] }],
       "icon": "resources/icon.icns",
       "hardenedRuntime": false,
       "gatekeeperAssess": false
     },
     "dmg": {
       "background": "resources/dmg-background.png",
       "window": { "width": 540, "height": 380 },
       "contents": [
         { "x": 130, "y": 220, "type": "file" },
         { "x": 410, "y": 220, "type": "link", "path": "/Applications" }
       ]
     },
     "extraResources": [
       { "from": "resources/python", "to": "python" },
       { "from": "../backend", "to": "backend",
         "filter": ["**/*", "!.venv/**", "!__pycache__/**", "!*.pyc", "!.env", "!tests/**"] }
     ],
     "afterSign": "scripts/notarize.js"
   }
   ```

3. **npm scripts**:
   - `"predist:mac": "bash ../scripts/download-python.sh"`
   - `"dist:mac": "npm run build && electron-builder --mac --universal"`

4. **`scripts/build-mac.sh`** — `download-python.sh` → `npm ci` → `npm run dist:mac`.

5. **`scripts/notarize.js`** — stub: `module.exports = async () => { /* TODO: notarize */ }`.

#### Success Criteria

- `bash scripts/build-mac.sh` completes.
- `scripts/test-bundle-structure.sh` passes.
- `lipo -info Resources/python/bin/python3` → `Architectures: arm64 x86_64`.
- Bundled Python reports `3.13.x`.
- `.dmg` mounts and the app launches.

---

### Phase 4 — First-Run Setup Wizard (Electron Renderer)

**Goal:** A guided 6-step wizard shown on first launch. Heavy work runs in the Electron main process via IPC; the wizard shows live progress.

#### Files to Create/Modify

| File | Action |
|---|---|
| `frontend/src/pages/SetupWizard/index.tsx` | Create — wizard root, state machine |
| `frontend/src/pages/SetupWizard/StepWelcome.tsx` | Create |
| `frontend/src/pages/SetupWizard/StepInstallDeps.tsx` | Create |
| `frontend/src/pages/SetupWizard/StepInitDb.tsx` | Create |
| `frontend/src/pages/SetupWizard/StepModelPicker.tsx` | Create |
| `frontend/src/pages/SetupWizard/StepDownloading.tsx` | Create |
| `frontend/src/pages/SetupWizard/StepDone.tsx` | Create |
| `frontend/src/pages/SetupWizard/SetupWizard.css` | Create |
| `frontend/src/pages/SetupWizard/__tests__/wizard.test.tsx` | Create — TDD first |
| `frontend/electron/main/ipc.ts` | Modify — setup IPC handlers |
| `frontend/electron/preload/index.ts` | Modify — expose setup channels |
| `frontend/src/types/electron.d.ts` | Modify — setup IPC types |

#### TDD: Write These Tests First

```typescript
// frontend/src/pages/SetupWizard/__tests__/wizard.test.tsx
test_starts_at_welcome_step()
test_advances_to_install_deps_on_continue()
test_install_deps_calls_ipc()
test_progress_bar_updates_on_progress_event()   // setup:install-deps-progress { percent: 50 }
test_model_picker_renders_all_models()          // 6 models + "Skip all optional" checkbox
test_model_picker_calculates_total_size()       // CLIP + embedding → ~610 MB shown
test_clip_and_embedding_cannot_be_deselected()  // required models are always checked
test_download_step_shows_per_model_progress()   // one progress bar per selected model
test_cancel_download_calls_ipc()
test_done_step_shows_launch_button()
```

#### Model Catalogue

```typescript
const MODELS = [
  { id: 'clip',        name: 'CLIP ViT-B-32',          size: '330 MB',  required: true,  desc: 'Required for photo tagging' },
  { id: 'embedding',   name: 'nomic-embed-text-v1.5',  size: '280 MB',  required: true,  desc: 'Required for semantic search' },
  { id: 'vision',      name: 'Qwen2-VL-2B',            size: '6 GB',    required: false, desc: 'Local image descriptions' },
  { id: 'translation', name: 'NLLB-200 Distilled',     size: '2.5 GB',  required: false, desc: 'Auto-translation' },
  { id: 'ocr',         name: 'TrOCR-small',             size: '150 MB',  required: false, desc: 'Text extraction from photos' },
  { id: 'chat',        name: 'Qwen2.5-Coder-3B',       size: '7 GB',    required: false, desc: 'Local AI assistant' },
]
```

#### IPC Channels (Main Process)

| Channel | Direction | Payload | Description |
|---|---|---|---|
| `setup:check-needed` | renderer→main | — | Returns `{ needed: boolean }` |
| `setup:install-deps` | renderer→main | — | Runs `python3 -m venv + pip install` |
| `setup:install-deps-progress` | main→renderer | `{ line, percent }` | Live log lines |
| `setup:init-db` | renderer→main | — | Runs `full_install.py` |
| `setup:download-model` | renderer→main | `{ modelId }` | Starts model download |
| `setup:download-model-progress` | main→renderer | `{ modelId, percent, bytes }` | Per-model progress |
| `setup:cancel-download` | renderer→main | — | Kills current download |
| `setup:complete` | renderer→main | — | Writes `setup_done` marker, calls `startBackend()` |

#### Generated `.env`

After setup, wizard writes `APP_DATA_DIR/.env` reflecting model choices: skipped optional models get `VISION_MODE=remote`, etc. Never overwritten on subsequent launches — only new keys appended.

#### Success Criteria

- All Vitest tests pass.
- On first launch: wizard renders, not main app.
- After wizard completes: `APP_DATA_DIR/venv/` exists, `db.sqlite3` has schema.
- On subsequent launches: wizard is skipped.
- Wizard can be re-triggered via Settings → "Reinstall / Reset".

---

### Phase 5 — Tesseract Detection

**Goal:** Handle the Tesseract OCR system dependency gracefully.

**Decision: Option A — detect and inform.** Option B (bundle Tesseract binary) is documented for future.

#### Files to Create/Modify

| File | Action |
|---|---|
| `backend/src/main.py` | Modify — add `GET /api/system/tesseract/` |
| `frontend/src/components/ui/TesseractBanner.tsx` | Create |
| `frontend/src/App.tsx` | Modify — fetch status on mount, show banner |

#### TDD

```python
test_tesseract_endpoint_available()     # mock 'which tesseract' → returns path
test_tesseract_endpoint_unavailable()   # mock 'which tesseract' → fails → { available: false }
```
```typescript
test_banner_renders_when_unavailable()  # { available: false } → banner visible
test_banner_hidden_when_available()     # { available: true } → no banner
test_banner_hidden_when_ocr_remote()    # OCR mode=remote → no banner regardless
test_copy_button_copies_brew_command()  # clipboard API called with 'brew install tesseract'
```

#### Banner Content

> ⚠️ Tesseract OCR is not installed. OCR features will not work locally.
> Install via Homebrew: `brew install tesseract` [Copy] [Dismiss]

**Option B (future):** Bundle the Tesseract binary + English tessdata (~50 MB) in `Resources/tesseract/`. Set `TESSDATA_PREFIX` and prepend `Resources/tesseract/bin` to `PATH` before spawning the backend.

#### Success Criteria

- Missing Tesseract → non-blocking banner in UI.
- Banner absent when Tesseract installed or OCR mode is remote.
- OCR tasks fail gracefully with a clear message.

---

### Phase 6 — DMG Polish

**Goal:** A professional `.dmg` with correct icon, background, and user-facing documentation.

#### Files to Create

| File | Description |
|---|---|
| `frontend/resources/icon-source.png` | 1024×1024 source PNG |
| `frontend/resources/icon.icns` | Generated by `make-icns.sh` |
| `frontend/resources/dmg-background.png` | 540×380 px DMG background |
| `scripts/make-icns.sh` | Uses `iconutil` to generate `.icns` from source PNG |
| `README-installer.md` | User-facing install guide |

#### `make-icns.sh` Steps

```bash
mkdir MyIcon.iconset
sips -z 16 16     icon-source.png --out MyIcon.iconset/icon_16x16.png
# ... all 10 required sizes ...
iconutil -c icns MyIcon.iconset -o icon.icns
```

#### `README-installer.md` Contents

- System requirements: macOS 13+ (Ventura), Apple Silicon or Intel
- Download and drag-to-Applications steps
- Gatekeeper note: right-click → Open if blocked
- First-launch wizard walkthrough
- Disk space: ~2 GB base + up to 16 GB models
- Tesseract install for OCR: `brew install tesseract`
- Uninstall: delete `PhotoDescriber2.app` + `~/Library/Application Support/PhotoDescriber2/`

#### Success Criteria

- DMG mounts with correct background and icon positions.
- App icon renders correctly in Dock and Finder at all sizes.
- `README-installer.md` is accurate.

---

### Phase 7 — Tests & CI

**Goal:** GitHub Actions workflow that builds the `.dmg` on every push to `main`.

#### Files to Create

| File | Action |
|---|---|
| `.github/workflows/build-mac.yml` | Create |
| `scripts/test-integration.sh` | Create — smoke test |
| `frontend/tests/e2e/installer.spec.ts` | Create — Playwright |

#### GitHub Actions Workflow

```yaml
name: Build macOS
on:
  push: { branches: [main] }
  pull_request: { branches: [main] }

jobs:
  build:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: bash scripts/download-python.sh
      - run: cd frontend && npm ci
      - run: bash scripts/build-mac.sh
      - uses: actions/upload-artifact@v4
        with:
          name: PhotoDescriber2-macOS
          path: frontend/dist-electron/*.dmg
          retention-days: 14
```

#### Integration Smoke Test (`test-integration.sh`)

1. Unpack `.app` to temp dir.
2. Spawn `Resources/python/bin/python3 Resources/backend/run.py` with temp `APP_DATA_DIR`.
3. Poll `GET http://localhost:$PORT/api/system/status/` for 30 s.
4. Assert HTTP 200.
5. Kill backend, assert `$APP_DATA_DIR/db.sqlite3` was created.

#### Manual Test Checklist

```
[ ] Fresh install — Apple Silicon Mac (macOS 13+)
[ ] Fresh install — Intel Mac (macOS 13+)
[ ] DMG mounts without Gatekeeper blocking
[ ] Drag to Applications works
[ ] First launch → setup wizard, not main app
[ ] Step 2: Install deps completes
[ ] Step 3: DB init — db.sqlite3 created in ~/Library/Application Support/PhotoDescriber2/
[ ] Step 4: Deselect all optional models → "Skip all" works
[ ] Step 5: Download CLIP + embedding (~610 MB) completes with progress
[ ] Step 6: Launch opens main app
[ ] Quit and relaunch → no wizard, main app opens directly
[ ] Tesseract banner: appears when Tesseract absent, absent when installed
[ ] Uninstall: delete app + APP_DATA_DIR → relaunch triggers wizard again
```

---

## 3. Complete File Tree

```
Photo_describer2/
├── .github/workflows/
│   └── build-mac.yml                            [CREATE]
├── scripts/
│   ├── download-python.sh                       [CREATE]
│   ├── build-mac.sh                             [CREATE]
│   ├── make-icns.sh                             [CREATE]
│   ├── notarize.js                              [CREATE — stub]
│   └── test-bundle-structure.sh                 [CREATE]
├── backend/
│   ├── src/
│   │   ├── data_dir.py                          [CREATE]
│   │   ├── config.py                            [MODIFY]
│   │   ├── main.py                              [MODIFY — /api/system/tesseract/]
│   │   └── queues/
│   │       ├── clip_queue.py                    [MODIFY — QUEUE_DB_DIR]
│   │       ├── embedding_queue.py               [MODIFY]
│   │       ├── folder_scan_queue.py             [MODIFY]
│   │       ├── ocr_queue.py                     [MODIFY]
│   │       ├── translation_queue.py             [MODIFY]
│   │       └── vision_queue.py                  [MODIFY]
│   ├── run.py                                   [MODIFY — call migrate_legacy_data]
│   └── tests/
│       └── test_data_dir.py                     [CREATE]
├── frontend/
│   ├── package.json                             [MODIFY — build config]
│   ├── resources/
│   │   ├── icon-source.png                      [CREATE]
│   │   ├── icon.icns                            [CREATE — generated]
│   │   ├── dmg-background.png                   [CREATE]
│   │   ├── splash.html                          [CREATE]
│   │   └── python/                              [CREATE — by download-python.sh]
│   ├── electron/main/
│   │   ├── backend.ts                           [MODIFY — real implementation]
│   │   ├── index.ts                             [MODIFY — lifecycle + splash]
│   │   ├── ipc.ts                               [MODIFY — setup channels]
│   │   └── __tests__/backend.test.ts            [MODIFY]
│   ├── electron/preload/
│   │   └── index.ts                             [MODIFY]
│   └── src/
│       ├── App.tsx                              [MODIFY]
│       ├── types/electron.d.ts                  [MODIFY]
│       ├── components/ui/
│       │   └── TesseractBanner.tsx              [CREATE]
│       ├── pages/SetupWizard/
│       │   ├── index.tsx                        [CREATE]
│       │   ├── StepWelcome.tsx                  [CREATE]
│       │   ├── StepInstallDeps.tsx              [CREATE]
│       │   ├── StepInitDb.tsx                   [CREATE]
│       │   ├── StepModelPicker.tsx              [CREATE]
│       │   ├── StepDownloading.tsx              [CREATE]
│       │   ├── StepDone.tsx                     [CREATE]
│       │   ├── SetupWizard.css                  [CREATE]
│       │   └── __tests__/wizard.test.tsx        [CREATE]
│       └── tests/e2e/
│           └── installer.spec.ts                [CREATE]
└── README-installer.md                          [CREATE]
```

---

## 4. Key Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Bundled Python quarantined by Gatekeeper | `xattr -dr com.apple.quarantine` after extraction; ad-hoc `codesign` for long term |
| Huey workers orphaned when Electron quits | Spawn `run.py` with `detached: true`; kill entire process group with `process.kill(-pid, 'SIGTERM')` |
| Queue DBs land inside read-only `.app` | `QUEUE_DB_DIR` env var points workers to `APP_DATA_DIR`; fallback only used in dev |
| `python-build-standalone` missing `pip` | Use `install_only` flavour which includes `ensurepip`; `get-pip.py` fallback |
| 16 GB model downloads fail mid-way | Per-model retry button; HuggingFace uses atomic writes so partial downloads are discarded cleanly |
| `app.getPath('userData')` returns `Electron` in dev | `app.setName('PhotoDescriber2')` before `app.whenReady()` forces correct path |
| SQLite WAL files corrupted during migration | Checkpoint WAL before copying; also copy `.wal` and `.shm` files |
| Universal binary doubles Python size | Use `lipo` only for the `python3` executable; pure-Python files are arch-independent |

---

## 5. Implementation Sequence

```
Phase 1 (data dir migration)
    └── Phase 2 (backend lifecycle)
            └── Phase 4 (setup wizard)
    └── Phase 3 (bundle Python + build)
            └── Phase 6 (DMG polish)
                    └── Phase 7 (CI)
Phase 5 (Tesseract) ← independent, parallel with Phase 3
```

**Estimated effort:** ~7 working days total
- Phase 1: 1 day
- Phase 2: 1.5 days
- Phase 3: 1 day
- Phase 4: 2 days
- Phase 5: 0.5 days
- Phase 6: 0.5 days
- Phase 7: 0.5 days

---

## 6. Out of Scope

- **Linux** — `data_dir.py` includes Linux path logic; AppImage/Flatpak packaging is a future phase.
- **Windows** — no Windows support planned; process management requires different signals.
- **Code signing / notarization** — `notarize.js` stub is a placeholder. Steps when ready: Apple Developer Program → Developer ID cert → set `hardenedRuntime: true` → configure GitHub Actions secrets → implement `@electron/notarize`.
- **LaunchAgent / auto-start** — backend starts/stops with the app window by user decision.
- **Auto-update** — users download new `.dmg` releases manually from GitHub Releases.
- **Postgres backend** — SQLite only for packaged installs.
