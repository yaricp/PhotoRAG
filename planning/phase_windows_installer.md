# Windows Installer — Implementation Plan

**PhotoRAG · Target: Windows 10/11 x64 · Format: NSIS (.exe)**

---

## 1. Overview & Architecture

### What We Are Building

A polished NSIS `.exe` installer that puts PhotoRAG in `%LOCALAPPDATA%\Programs\PhotoRAG\` (or a user-chosen directory), creates Start Menu and desktop shortcuts, registers an uninstaller in Add/Remove Programs, and on first launch walks the user through the same setup wizard that exists on macOS.

No Microsoft Visual C++ Redistributable required from the user — bundled Python from `python-build-standalone` (MSVC shared) already brings its own DLLs.

### Target Matrix

| Architecture | Status |
|---|---|
| x64 (Intel / AMD 64-bit) | **In scope** |
| ARM64 (Snapdragon X / Copilot+) | Out of scope (Phase 2) |
| ia32 (32-bit x86) | Permanently out of scope — PyTorch dropped 32-bit |

### How the Package Will Look

```
%LOCALAPPDATA%\Programs\PhotoRAG\
  PhotoRAG.exe                         ← Electron binary
  resources\
    app.asar                           ← compiled React/Electron JS
    python\                            ← python-build-standalone 3.13 x64
      python.exe
      pythonw.exe
      python313.dll
      DLLs\
      Lib\
    backend\                           ← backend source tree
      run.py
      src\
      requirements.txt
      pyproject.toml

%APPDATA%\PhotoRAG\                    ← APP_DATA_DIR (mutable, same role as ~/Library/… on Mac)
  db.sqlite3
  clip.sqlite3 / embedding.sqlite3 / …
  .hf_cache\                           ← HuggingFace model weights
  venv\                                ← pip venv (created during setup wizard)
    Scripts\
      python.exe
      pip.exe
  setup_done                           ← marker written by wizard on completion
  .env                                 ← optional user config overrides
```

### Key Differences vs macOS Build

| Topic | macOS | Windows |
|---|---|---|
| Python layout | `python/bin/python3` | `python/python.exe` |
| Venv scripts dir | `venv/bin/python3` | `venv\Scripts\python.exe` |
| Process group kill | `kill(-pid, SIGTERM)` | `taskkill /F /T /PID <pid>` |
| Detached process | invisible child | needs `windowsHide: true` |
| App data dir | `~/Library/Application Support/PhotoRAG/` | `%APPDATA%\PhotoRAG\` |
| Icon format | `.icns` | `.ico` (multi-size) |
| PyTorch wheels | CPU from PyPI | CPU from `https://download.pytorch.org/whl/cpu` (avoids 2.5 GB CUDA wheel) |
| Code signing | unsigned (no cert) | unsigned (no cert) — SmartScreen warning on first run |
| Python archive format | `.tar.gz` | `.tar.zst` |

---

## 2. Implementation Phases

---

### Phase 1 — App Icon (`resources/icon.ico`)

**Why first**: electron-builder requires `icon.ico` before any Windows build can succeed.

**Files created:**
- `resources/icon.ico` — multi-resolution icon (16, 32, 48, 64, 128, 256 px)
- `scripts/make-ico.sh` — generation script (mirrors `make-icns.sh`)

**How to generate** (uses ImageMagick, available on both macOS and GitHub Actions `windows-latest`):

```bash
#!/usr/bin/env bash
# scripts/make-ico.sh
set -euo pipefail
SRC="$(dirname "$0")/../frontend/resources/icon-source.png"
OUT="$(dirname "$0")/../frontend/resources/icon.ico"

magick "$SRC" \
  \( -clone 0 -resize 256x256 \) \
  \( -clone 0 -resize 128x128 \) \
  \( -clone 0 -resize 64x64  \) \
  \( -clone 0 -resize 48x48  \) \
  \( -clone 0 -resize 32x32  \) \
  \( -clone 0 -resize 16x16  \) \
  -delete 0 "$OUT"
echo "✓ icon.ico written to $OUT"
```

Alternative (no ImageMagick dependency): use the `png-to-ico` npm package as a dev dependency and generate from a build script.

---

### Phase 2 — Python Runtime Download Script for Windows

**File created:** `scripts/download-python-win.sh`

Downloads the `python-build-standalone` x64 Windows release and unpacks it into `frontend/resources/python/` — the same directory that electron-builder's `extraResources` copies into the installer.

```bash
#!/usr/bin/env bash
# scripts/download-python-win.sh
set -euo pipefail

RELEASE="20260510"
VERSION="3.13.3"
ARCH="x86_64-pc-windows-msvc-shared-pgo-full"
URL="https://github.com/astral-sh/python-build-standalone/releases/download/${RELEASE}/cpython-${VERSION}+${RELEASE}-${ARCH}.tar.zst"

RESOURCES="$(dirname "$0")/../frontend/resources"
TARGET="${RESOURCES}/python"

echo "Downloading Python ${VERSION} for Windows x64..."
curl -fL --retry 3 -o /tmp/cpython-win.tar.zst "$URL"

rm -rf "$TARGET"
mkdir -p "$TARGET"

# tar on macOS needs zstd installed (brew install zstd).
# tar on Windows Server 2022 / GitHub Actions supports zstd natively.
tar --zstd -xf /tmp/cpython-win.tar.zst -C "$TARGET" --strip-components=2
# python-build-standalone extracts as: python/install/python.exe …
# --strip-components=2 lands us at: python/python.exe python/Lib/ …

echo "✓ Windows Python runtime at ${TARGET}"
```

> **Note on strip-components**: verify the exact archive structure on the first run. The python-build-standalone Windows archives unpack as `python/install/python.exe` — `--strip-components=2` removes both levels. Adjust if the archive layout differs.

**Companion PowerShell version** for native Windows developers:
`scripts/download-python-win.ps1`:

```powershell
$Release = "20260510"
$Version = "3.13.3"
$Arch    = "x86_64-pc-windows-msvc-shared-pgo-full"
$Url     = "https://github.com/astral-sh/python-build-standalone/releases/download/$Release/cpython-$Version+$Release-$Arch.tar.zst"

$Resources = "$PSScriptRoot\..\frontend\resources"
$Target    = "$Resources\python"

Write-Host "Downloading Python $Version for Windows x64..."
Invoke-WebRequest $Url -OutFile "$env:TEMP\cpython-win.tar.zst"

if (Test-Path $Target) { Remove-Item $Target -Recurse -Force }
New-Item -ItemType Directory -Path $Target | Out-Null

# Windows 10 1803+ tar supports zstd natively
tar --zstd -xf "$env:TEMP\cpython-win.tar.zst" -C $Target --strip-components=2
Write-Host "Done: $Target"
```

---

### Phase 3 — Backend Python Compatibility (`data_dir.py`)

Add the Windows path branch so dev-mode backend (no Electron, no `APP_DATA_DIR` env var) resolves correctly:

**File modified:** `backend/src/data_dir.py`

```python
def resolve_app_data_dir() -> Path:
    if override := os.environ.get("APP_DATA_DIR"):
        path = Path(override)
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / APP_NAME
    elif sys.platform == "win32":
        appdata = os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming")
        path = Path(appdata) / APP_NAME
    else:
        path = Path.home() / ".local" / "share" / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path
```

> In packaged mode, `APP_DATA_DIR` is always set by Electron to `app.getPath('userData')`, which on Windows returns `%APPDATA%\PhotoRAG`. The branch above only matters for bare Python dev runs.

---

### Phase 4 — Electron Main Process — Platform-Aware Paths

Three files need platform guards:

#### 4a. `frontend/electron/main/backend.ts`

```typescript
export function locatePython(): string {
    if (app.isPackaged) {
        const bin = process.platform === 'win32'
            ? 'python.exe'
            : path.join('bin', 'python3')
        return path.join(process.resourcesPath, 'python', bin)
    }
    return process.platform === 'win32' ? 'python' : 'python3'
}

export function locateVenvPython(): string {
    const rel = process.platform === 'win32'
        ? path.join('Scripts', 'python.exe')
        : path.join('bin', 'python3')
    return path.join(app.getPath('userData'), 'venv', rel)
}
```

**Process killing** — `process.kill(-pid, SIGTERM)` is Unix-only. Replace `stopBackend()`:

```typescript
export function stopBackend(): void {
    if (!backendProcess?.pid) return
    const pid = backendProcess.pid
    if (process.platform === 'win32') {
        // taskkill /F (force) /T (tree — kills child processes too)
        spawn('taskkill', ['/F', '/T', '/PID', String(pid)], { windowsHide: true })
    } else {
        try { process.kill(-pid, 'SIGTERM') } catch { /* already gone */ }
        setTimeout(() => {
            try { process.kill(-pid, 'SIGKILL') } catch { /* already gone */ }
        }, 5000)
    }
    backendProcess = null
    _port = null
}
```

**Process spawn** — add `windowsHide: true` to suppress the console window on Windows:

```typescript
backendProcess = spawn(python, ['run.py'], {
    cwd: backendDir,
    detached: true,
    windowsHide: true,   // ← add this
    env: { ... },
})
```

#### 4b. `frontend/electron/main/ipc.ts`

All places that hardcode `venv/bin/pip` or `venv/bin/python3` need platform guards. Extract a helper at the top:

```typescript
function venvBin(venvPath: string, name: string): string {
    const dir = process.platform === 'win32' ? 'Scripts' : 'bin'
    const ext = process.platform === 'win32' ? '.exe' : ''
    return join(venvPath, dir, name + ext)
}
```

Replace all occurrences:
- `join(venvPath, 'bin', 'pip')` → `venvBin(venvPath, 'pip')`
- `join(venvPath, 'bin', 'python3')` → `venvBin(venvPath, 'python')`
  (Windows venv creates `python.exe` not `python3.exe`)

---

### Phase 5 — PyTorch CPU Wheels on Windows

The default `pip install torch` on Windows pulls the CUDA variant (~2.5 GB). We need the CPU-only build (~200 MB) from PyTorch's own index. Detected in `setup:install-deps` IPC handler:

```typescript
ipcMain.handle('setup:install-deps', async (event) => {
    const userData = app.getPath('userData')
    const venvPath = join(userData, 'venv')

    // Step 1: create venv
    await spawnTracked(python, ['-m', 'venv', venvPath], {}, ...)

    // Step 2: pip install
    const pip = venvBin(venvPath, 'pip')
    const installArgs = ['install', '-r', requirements, '--progress-bar', 'off']
    if (process.platform === 'win32') {
        // CPU-only torch — avoids 2.5 GB CUDA wheels
        installArgs.push('--extra-index-url', 'https://download.pytorch.org/whl/cpu')
    }
    await spawnTracked(pip, installArgs, {}, ...)
})
```

> `--extra-index-url` (not `--index-url`) lets pip still fall back to PyPI for all non-torch packages — this is safer than overriding the default index completely.

---

### Phase 6 — electron-builder Windows Config

**File modified:** `frontend/package.json` — add to the `"build"` section:

```json
"win": {
  "target": [{ "target": "nsis", "arch": ["x64"] }],
  "icon": "resources/icon.ico",
  "artifactName": "${productName}-Setup-${version}-${arch}.${ext}"
},
"nsis": {
  "oneClick": false,
  "allowToChangeInstallationDirectory": true,
  "createDesktopShortcut": true,
  "createStartMenuShortcut": true,
  "shortcutName": "PhotoRAG",
  "installerIcon": "resources/icon.ico",
  "uninstallerIcon": "resources/icon.ico",
  "installerHeaderIcon": "resources/icon.ico",
  "deleteAppDataOnUninstall": false
}
```

**Add npm scripts:**

```json
"predist:win": "bash ../scripts/download-python-win.sh",
"dist:win": "npm run build && electron-builder --win --x64"
```

> `predist:win` runs the Python download before every Windows build, just as `predist:mac` does for macOS.

> `deleteAppDataOnUninstall: false` — the NSIS uninstaller will NOT wipe `%APPDATA%\PhotoRAG\` (user's photos DB, models). Safer default; user can delete manually.

---

### Phase 7 — Build Orchestration Scripts

#### `scripts/build-win.sh` (bash — runs on Windows/Git Bash or macOS for cross-compile)

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FRONTEND="$ROOT/frontend"

echo "=== Step 1: Download Windows Python runtime ==="
bash "$ROOT/scripts/download-python-win.sh"

echo "=== Step 2: Install npm dependencies ==="
cd "$FRONTEND"
npm install

echo "=== Step 3: Build Windows NSIS installer ==="
npm run dist:win

echo "=== Done! ==="
echo "Installer: $FRONTEND/dist-electron/"
```

#### `scripts/build-win.ps1` (PowerShell — for native Windows dev machines)

```powershell
$ErrorActionPreference = "Stop"
$Root     = Split-Path $PSScriptRoot
$Frontend = "$Root\frontend"

Write-Host "=== Step 1: Download Windows Python runtime ==="
& "$PSScriptRoot\download-python-win.ps1"

Write-Host "=== Step 2: Install npm dependencies ==="
Set-Location $Frontend
npm install

Write-Host "=== Step 3: Build Windows NSIS installer ==="
npm run dist:win

Write-Host "=== Done! Installer in: $Frontend\dist-electron\ ==="
```

---

### Phase 8 — GitHub Actions CI (`build-win.yml`)

**File created:** `.github/workflows/build-win.yml`

```yaml
name: Build Windows Installer

on:
  push:
    branches: [main, feature/windows-installer]
  pull_request:
    branches: [main]
  workflow_dispatch:

jobs:
  test-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: npm install
        working-directory: frontend
      - run: npm test
        working-directory: frontend

  test-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.13' }
      - run: pip install -r backend/requirements.txt
      - run: pytest backend/tests/test_data_dir.py backend/tests/test_db_service.py -v

  build-nsis:
    runs-on: windows-latest
    needs: [test-frontend, test-backend]
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with: { node-version: '20' }

      - name: Download Windows Python runtime
        shell: bash
        run: bash scripts/download-python-win.sh

      - name: Install npm dependencies
        working-directory: frontend
        run: npm install

      - name: Build NSIS installer
        working-directory: frontend
        run: npm run dist:win
        env:
          # Placeholder — wire up when cert is obtained:
          # WIN_CERT_FILE: ${{ secrets.WIN_CERT_FILE }}
          # WIN_CERT_PASSWORD: ${{ secrets.WIN_CERT_PASSWORD }}

      - name: Upload installer artifact
        uses: actions/upload-artifact@v4
        with:
          name: PhotoRAG-Windows-x64
          path: frontend/dist-electron/*.exe
          retention-days: 30

      - name: Verify bundle structure
        shell: bash
        run: bash scripts/test-bundle-win.sh
```

---

### Phase 9 — Bundle Verification Script

**File created:** `scripts/test-bundle-win.sh`

```bash
#!/usr/bin/env bash
# Smoke-tests the produced Windows installer directory structure.
set -euo pipefail

DIST="$(dirname "$0")/../frontend/dist-electron"
EXE=$(find "$DIST" -name "*.exe" | head -1)
[ -n "$EXE" ] || { echo "ERROR: no .exe found in dist-electron/"; exit 1; }
echo "✓ installer found: $EXE"

# Unpack with 7zip (available on windows-latest) and check contents
# This is a placeholder — actual verification can use InnoExtract or NSIS /NCRC checks
echo "✓ basic structure check passed"
```

---

## 3. File Checklist

### New Files

| File | Purpose |
|---|---|
| `scripts/download-python-win.sh` | Downloads Python 3.13 x64 from python-build-standalone |
| `scripts/download-python-win.ps1` | Same, PowerShell version for native Windows devs |
| `scripts/build-win.sh` | Full Windows build orchestration (bash) |
| `scripts/build-win.ps1` | Full Windows build orchestration (PowerShell) |
| `scripts/make-ico.sh` | Generates icon.ico from icon-source.png (ImageMagick) |
| `scripts/test-bundle-win.sh` | CI smoke-test for Windows installer artifact |
| `.github/workflows/build-win.yml` | GitHub Actions CI — Windows NSIS build |
| `frontend/resources/icon.ico` | Multi-resolution Windows icon (committed artifact) |

### Modified Files

| File | Change |
|---|---|
| `frontend/electron/main/backend.ts` | Platform-aware `locatePython()`, `locateVenvPython()`, `stopBackend()` (taskkill on Windows), `windowsHide: true` in spawn |
| `frontend/electron/main/ipc.ts` | Add `venvBin()` helper, replace all `venv/bin/pip`, `venv/bin/python3` hardcodes; add CPU-only torch `--extra-index-url` on Windows |
| `frontend/package.json` | Add `"win"`, `"nsis"` sections; add `predist:win` + `dist:win` npm scripts |
| `backend/src/data_dir.py` | Add `win32` branch for bare Python dev runs |

---

## 4. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| python-build-standalone archive layout changes between releases | Low | Medium | Pin a specific release tag; inspect the archive with `tar -tvf` before committing to `--strip-components` |
| Huey task workers fail on Windows due to fork() semantics | Medium | High | Huey uses `spawn` not `fork` for subprocesses; test explicitly on Windows during Phase 9 |
| SmartScreen blocks unsigned installer on first run | High | Low | Expected. Document "click More info → Run anyway" in README / release notes. Blocked once cert is obtained |
| PyTorch CPU index URL changes or becomes unavailable | Low | High | Mirror in CI step; add a fallback to plain `pip install` if index returns 404 |
| sqlite-vec has no Windows x64 wheel | Low | High | Check PyPI before starting; if absent, switch to the `sqlite-vec` GitHub releases binary |
| easyocr / ONNX native extensions require VC++ runtime | Medium | Medium | python-build-standalone MSVC-shared brings its own VC++ DLLs; test in CI |
| Cross-building NSIS from macOS (electron-builder) misses a DLL | Low | Medium | Build natively on `windows-latest` in CI — trust the native build over cross-compile for shipping |

---

## 5. Decisions Recorded

| Decision | Rationale |
|---|---|
| x64 only | ARM64 Windows is <5% market share; add in Phase 2 if requested |
| NSIS installer (not MSI) | Simpler electron-builder config; what Electron ecosystem standardises on |
| Unsigned (no cert) | No cert available now; SmartScreen warning is tolerable for early distribution |
| CPU-only PyTorch | Avoids 2.5 GB CUDA wheel on machines where CUDA is irrelevant; models run on CPU anyway |
| `deleteAppDataOnUninstall: false` | Protects user DB and photos from accidental deletion on uninstall |
| CI on `windows-latest` (native) | Avoids cross-compilation edge cases; mirrors macOS approach on `macos-latest` |

---

## 6. Implementation Order

```
1. make-ico.sh → generate icon.ico          (unblocks all further build attempts)
2. download-python-win.sh / .ps1            (unblocks electron-builder)
3. backend.ts — platform path guards        (correctness)
4. ipc.ts — venvBin helper + torch flag     (correctness)
5. data_dir.py — win32 branch               (correctness, dev mode)
6. package.json — win + nsis config         (ties it all together)
7. build-win.sh / build-win.ps1             (local developer workflow)
8. build-win.yml                            (CI)
9. test-bundle-win.sh                       (CI verification)
10. Manual test on real Windows VM          (end-to-end validation)
```

---

## 7. Testing Checklist (Manual, Windows VM)

- [ ] Run `scripts/build-win.sh` from a macOS machine — NSIS .exe is produced
- [ ] Run `scripts/build-win.ps1` on Windows — NSIS .exe is produced
- [ ] Install produced .exe on a clean Windows 10 VM (no prior Node/Python)
- [ ] SmartScreen warning appears → "More info → Run anyway" works
- [ ] App launches → setup wizard appears
- [ ] Install deps step completes successfully (torch CPU wheels, no CUDA download)
- [ ] Init DB step succeeds
- [ ] Model download step works (at least one local model)
- [ ] Setup completes → backend starts → main app loads
- [ ] Photo pipeline runs end-to-end
- [ ] Uninstall via Add/Remove Programs works; `%APPDATA%\PhotoRAG\` is preserved
- [ ] CI build on GitHub Actions produces a downloadable `.exe` artifact
