# Frontend Implementation Plan — Photo Describer 2 (Electron-First)

> **Stack**: Electron 30 + electron-vite + React 18 + TypeScript + Vanilla CSS  
> **Approach**: TDD — write tests first, then implement  
> **Target**: Cross-platform desktop app (.app / .exe) with embedded Python backend  
> **Phase**: Browser-compatible SPA now, Electron shell wraps it without rewrites later

---

## Why Electron Changes Everything

The original `implementation_plan.md` explicitly calls for packaging as a **standalone `.exe`/`.app`**. This means:

| Concern | Browser-only approach | Electron-first approach |
|---|---|---|
| **Image serving** | Need new `/api/photos/{id}/image` endpoint | Register `app://` custom protocol in Main process → serve `file_path` directly |
| **API base URL** | Hardcoded `localhost:8000` env var | Main process spawns Python, discovers port, sends to Renderer via IPC |
| **Directory picker** | `<input type="file">` (limited) | `dialog.showOpenDialog()` via IPC → native OS picker |
| **CORS** | Must configure FastAPI CORS | Not needed — same-origin in Electron renderer |
| **Distribution** | Deploy to web server | Electron Builder bundles Renderer + PyInstaller bundle |
| **DB/model paths** | Relative to cwd | `app.getPath('userData')` — safe, cross-platform |
| **File system** | No direct FS access | Main process has full Node.js FS via IPC |

---

## Architecture: Three-Process Design

```
┌─────────────────────────────────────────────────────────────────┐
│  Electron Main Process (Node.js)                                │
│  ├── Spawns Python FastAPI backend (child_process / bundled)    │
│  ├── Discovers backend port, stores in app state               │
│  ├── Registers app:// protocol → serves local image files      │
│  ├── IPC handlers: dialog.showOpenDialog, backend-port, quit   │
│  └── Manages app lifecycle (tray, auto-update, window)         │
├─────────────────────────────────────────────────────────────────┤
│  Preload Script (contextBridge — sandboxed Node bridge)         │
│  └── window.electronAPI = { openFolder, getBackendPort,        │
│                              onBackendReady, platform }         │
├─────────────────────────────────────────────────────────────────┤
│  Renderer Process (React SPA — same as browser)                 │
│  ├── Never calls Node APIs directly                             │
│  ├── All native features via window.electronAPI                 │
│  └── API calls → http://localhost:{port}/api/...               │
├─────────────────────────────────────────────────────────────────┤
│  Python Backend (child process)                                 │
│  ├── FastAPI on dynamic port (8000, or next available)          │
│  └── SQLite + AI models in userData dir                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
frontend/                          ← electron-vite monorepo
├── electron/
│   ├── main/
│   │   ├── index.ts               # App lifecycle, window, protocol
│   │   ├── backend.ts             # Spawn/manage Python backend process
│   │   ├── protocol.ts            # app:// → local file serving
│   │   └── ipc.ts                 # All IPC handler registrations
│   └── preload/
│       └── index.ts               # contextBridge definitions
├── src/                           # Renderer (React) — identical to browser
│   ├── api/
│   │   ├── client.ts              # Typed fetch client
│   │   └── base.ts                # Gets base URL from electronAPI or env
│   ├── components/
│   │   ├── ui/                    # Design system atoms
│   │   └── photos/                # Domain components
│   ├── pages/                     # Route pages
│   ├── hooks/                     # usePhotos, useSSE, useSearch, useElectron
│   ├── stores/                    # Zustand: gallery, search, chat, system
│   ├── styles/                    # tokens.css + global.css
│   ├── types/
│   │   ├── api.ts                 # Backend schema mirrors
│   │   └── electron.d.ts          # window.electronAPI type declarations
│   └── test/
│       ├── server.ts              # MSW handlers
│       └── factories.ts           # Data factories
├── tests/                         # Playwright E2E
├── electron-builder.yml           # Packaging config
├── electron.vite.config.ts        # electron-vite config
└── vitest.config.ts
```

---

## Proposed Changes

---

### Phase 0 — Scaffold & TDD Infrastructure

#### Bootstrap with `electron-vite`

```bash
cd /Users/yaricp/Projects/MyOwn/Photo_describer2
npx -y create-electron-vite@latest frontend -- --template react-ts
cd frontend && npm install
```

#### Additional dependencies

```bash
# Routing + state
npm install react-router-dom zustand

# Testing
npm install -D vitest @vitest/ui jsdom \
  @testing-library/react @testing-library/user-event \
  @testing-library/jest-dom msw

# E2E
npm install -D @playwright/test
npm install -D electron-playwright-helpers  # Electron-aware Playwright

# Packaging
npm install -D electron-builder
```

#### TDD Infrastructure

**`src/test/server.ts`** — MSW handlers for all 14 backend endpoints:
```typescript
import { http, HttpResponse } from 'msw'
const BASE = 'http://localhost:8000'

export const handlers = [
  http.get(`${BASE}/api/photos/`,       () => HttpResponse.json(paginatedPhotos)),
  http.get(`${BASE}/api/photos/:id`,    () => HttpResponse.json(mockPhoto)),
  http.delete(`${BASE}/api/photos/:id`, () => HttpResponse.json(mockPhoto)),
  http.post(`${BASE}/api/search/`,      () => HttpResponse.json([mockPhoto])),
  http.post(`${BASE}/api/chat/`,        () => HttpResponse.json(mockChatResponse)),
  http.get(`${BASE}/api/system/status/`,() => HttpResponse.json(mockStatuses)),
  http.get(`${BASE}/api/watchers/`,     () => HttpResponse.json([mockWatcher])),
  http.post(`${BASE}/api/watch/`,       () => HttpResponse.json(mockWatcher)),
  http.get(`${BASE}/api/tags/`,         () => HttpResponse.json([mockTag])),
  http.get(`${BASE}/api/categories/`,   () => HttpResponse.json([mockCategory])),
  http.get(`${BASE}/api/cameras/`,      () => HttpResponse.json([mockCamera])),
  http.get(`${BASE}/api/geopositions/`, () => HttpResponse.json([mockGeo])),
  http.get(`${BASE}/api/job/:photoId`,  () => HttpResponse.json(mockJob)),
  http.get(`${BASE}/api/stream/`,       () => new HttpResponse(null, { status: 200 })),
]
```

**`src/test/factories.ts`** — typed factory functions:
```typescript
export const makePhoto = (overrides?: Partial<Photo>): Photo => ({
  id: 1, file_path: '/Users/test/Photos/doc1.png',
  description: 'A formal document', is_doc: false, ...overrides
})
export const makeTag = (name = 'document'): PhotoTag => ({ tag: { id: 1, name }, confidence_score: 0.9 })
// …etc
```

**`src/types/electron.d.ts`** — window API contract:
```typescript
interface ElectronAPI {
  openFolder: () => Promise<string | null>     // native dir picker
  getBackendPort: () => Promise<number>         // port FastAPI is running on
  onBackendReady: (cb: (port: number) => void) => void
  platform: NodeJS.Platform                    // 'darwin' | 'win32' | 'linux'
}
declare global { interface Window { electronAPI?: ElectronAPI } }
```

---

### Phase 1 — Electron Main Process

#### [NEW] `electron/main/backend.ts`

Spawns and manages the Python FastAPI backend:

```typescript
import { spawn, ChildProcess } from 'child_process'
import { app } from 'electron'
import path from 'path'
import net from 'net'

async function findFreePort(start = 8000): Promise<number> { /* ... */ }

export async function startBackend(): Promise<number> {
  const port = await findFreePort()
  const userData = app.getPath('userData')
  
  // Dev: run Python directly. Prod: use PyInstaller bundle.
  const backendExe = app.isPackaged
    ? path.join(process.resourcesPath, 'backend', 'run')  // PyInstaller one-file
    : 'python'
  
  const args = app.isPackaged
    ? [`--port=${port}`, `--db-path=${userData}/photos.sqlite3`]
    : ['-m', 'uvicorn', 'src.main:app', '--port', String(port)]

  const proc: ChildProcess = spawn(backendExe, args, {
    cwd: app.isPackaged ? undefined : path.join(__dirname, '../../backend'),
    env: { ...process.env, WATCH_DIRECTORY: path.join(userData, 'photos') },
  })
  
  proc.stdout?.on('data', d => console.log('[backend]', d.toString()))
  proc.stderr?.on('data', d => console.error('[backend]', d.toString()))
  
  await waitForBackend(port)  // poll until FastAPI responds
  return port
}
```

#### [NEW] `electron/main/protocol.ts`

Registers `app://` custom protocol to serve local image files without a backend endpoint:

```typescript
import { protocol, net } from 'electron'
import path from 'path'

export function registerAppProtocol() {
  protocol.handle('app', (request) => {
    // app://local-image?path=/Users/me/Photos/doc1.png
    const url = new URL(request.url)
    const filePath = url.searchParams.get('path') ?? ''
    return net.fetch(`file://${filePath}`)
  })
}
```

**This completely eliminates the need for a `/api/photos/{id}/image` backend endpoint.**

#### [NEW] `electron/main/ipc.ts`

```typescript
import { ipcMain, dialog } from 'electron'

export function registerIpcHandlers(backendPort: number) {
  ipcMain.handle('open-folder', async () => {
    const result = await dialog.showOpenDialog({ properties: ['openDirectory'] })
    return result.canceled ? null : result.filePaths[0]
  })
  ipcMain.handle('get-backend-port', () => backendPort)
}
```

#### [NEW] `electron/preload/index.ts`

```typescript
import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('electronAPI', {
  openFolder:     () => ipcRenderer.invoke('open-folder'),
  getBackendPort: () => ipcRenderer.invoke('get-backend-port'),
  onBackendReady: (cb) => ipcRenderer.on('backend-ready', (_, port) => cb(port)),
  platform:       process.platform,
})
```

**Tests for Electron main** (`electron/main/__tests__/`):
```
backend.ts
  ✓ findFreePort returns available port
  ✓ waitForBackend resolves when server responds
  ✓ startBackend sets correct env vars

protocol.ts
  ✓ app:// URL with ?path= resolves to file://
  ✓ missing path returns 400

ipc.ts
  ✓ open-folder returns null when dialog cancelled
  ✓ get-backend-port returns the port passed in
```

---

### Phase 2 — API Client (Electron-Aware)

#### [NEW] `src/api/base.ts`

Resolves the backend base URL from Electron IPC or env:

```typescript
let _port: number | null = null

export async function getBaseUrl(): Promise<string> {
  if (_port) return `http://localhost:${_port}`
  
  if (window.electronAPI) {
    _port = await window.electronAPI.getBackendPort()
    return `http://localhost:${_port}`
  }
  
  // Browser dev fallback
  return import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
}
```

#### [NEW] `src/api/images.ts`

Converts `file_path` to a URL the renderer can display:

```typescript
export function photoImageUrl(filePath: string): string {
  if (window.electronAPI) {
    // Use custom app:// protocol registered in main process
    return `app://local-image?path=${encodeURIComponent(filePath)}`
  }
  // Browser dev: assume backend serves static files or use placeholder
  return `/api/static?path=${encodeURIComponent(filePath)}`
}
```

**Tests** (`src/api/__tests__/`):
```
base.ts
  ✓ uses electronAPI.getBackendPort() when in Electron
  ✓ falls back to VITE_API_BASE_URL in browser

images.ts
  ✓ returns app:// URL when electronAPI present
  ✓ returns /api/static URL when in browser
  ✓ path is URL-encoded
```

---

### Phase 3 — Design System & UI Atoms

#### [NEW] `src/styles/tokens.css`

Dark glassmorphism theme designed for a **desktop native app feel**:

```css
:root {
  --color-bg:          #0d0d12;
  --color-surface:     #16161f;
  --color-surface-2:   #1e1e2a;
  --color-glass:       rgba(30, 30, 42, 0.7);
  --color-border:      rgba(255,255,255,0.08);
  --color-accent:      #7c6fff;
  --color-accent-glow: rgba(124,111,255,0.35);
  --color-text:        #eaeaf5;
  --color-text-dim:    #7878a0;
  --color-success:     #34d399;
  --color-warning:     #fbbf24;
  --color-error:       #f87171;
  --color-doc:         #60a5fa;

  --font-sans: 'Inter', system-ui, -apple-system, sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', monospace;

  /* Electron: no text selection on UI elements (native app feel) */
  -webkit-user-select: none;
  user-select: none;
}

/* Allow text selection inside content areas */
.selectable { -webkit-user-select: text; user-select: text; }

/* Electron draggable titlebar region */
.titlebar { -webkit-app-region: drag; }
.titlebar button { -webkit-app-region: no-drag; }
```

#### UI Atoms — all tested before implemented

| Component | Key TDD scenarios |
|---|---|
| `Button` | primary/ghost/danger variants, loading spinner, disabled |
| `Badge` | tag/category/doc/processing/error colors |
| `Spinner` | sm/md/lg sizes |
| `Card` | glassmorphism surface, hover glow |
| `Modal` | Escape closes, focus trap, backdrop blur |
| `SearchBar` | Enter submits, clear button, debounce |
| `Tooltip` | show/hide on hover with delay |
| `EmptyState` | icon + title + description + optional CTA |
| `TitleBar` | custom Electron titlebar (close/minimize/maximize on Windows) |

---

### Phase 4 — Layout & Routing

#### [NEW] App shell with custom titlebar

```
┌──── TitleBar (draggable) ──────────── [_ □ ✕] ┐
│ ⬡ Photo Describer                              │
├─────────┬──────────────────────────────────────┤
│         │                                       │
│ Sidebar │       <Outlet /> (page content)       │
│         │                                       │
│ 🖼 Gallery │                                   │
│ 🔍 Search │                                    │
│ 📄 Docs  │                                     │
│ 🤖 Chat  │                                     │
│ ⚙ Settings│                                    │
│         │                                       │
│ ● ready │    (system status dot)                │
└─────────┴──────────────────────────────────────┘
```

Routes:
```
/          → GalleryPage
/search    → SearchPage
/photo/:id → PhotoDetailPage
/documents → DocumentsPage
/chat      → ChatPage
/settings  → SettingsPage
```

**Tests:**
```
App
  ✓ renders sidebar + outlet
  ✓ all 6 routes render correct page
  ✓ sidebar active link highlighted

TitleBar
  ✓ renders on win32 platform (window.electronAPI.platform)
  ✓ hidden on darwin (macOS native traffic lights)
```

---

### Phase 5 — Gallery Page

#### [NEW] `src/pages/GalleryPage.tsx`

```typescript
// PhotoCard uses photoImageUrl() for src:
<img src={photoImageUrl(photo.file_path)} alt={basename(photo.file_path)} />
```

**Features:** paginated grid, filter sidebar, processing badge, job polling

**TDD Test cases:**
```
PhotoCard
  ✓ img src uses app:// in Electron, /api/static in browser
  ✓ "Processing…" badge when job exists
  ✓ "Document" badge when is_doc=true
  ✓ top tag with confidence bar
  ✓ click → /photo/:id

GalleryPage
  ✓ fetches /api/photos/ via typed client
  ✓ renders cards from MSW response
  ✓ filter updates URL params
  ✓ job polling starts for processing photos
  ✓ card refreshes when job completes
```

**E2E (Playwright + electron-playwright-helpers):**
```typescript
import { _electron as electron } from 'playwright'

test('gallery loads photos', async () => {
  const app = await electron.launch({ args: ['dist-electron/main/index.js'] })
  const page = await app.firstWindow()
  await expect(page.locator('[data-testid="photo-card"]')).toHaveCount(3)
  await app.close()
})
```

---

### Phase 6 — Photo Detail Page

**Key Electron difference:** image zoom uses `app://` URL; copy-to-clipboard uses `navigator.clipboard` (works in Electron renderer).

**TDD Test cases:**
```
PhotoImage
  ✓ src is app:// URL in Electron context
  ✓ skeleton shown during load
  ✓ zoom modal opens on click

PhotoDetail
  ✓ description, tags with % bars, geo, camera
  ✓ OcrPanel shown only when is_doc=true
  ✓ ocr_text copy uses navigator.clipboard.writeText
  ✓ delete → DELETE /api/photos/:id → back to /
  ✓ confirmation modal before delete
```

---

### Phase 7 — Settings Page (Electron-Enhanced)

#### Native directory picker via IPC

```typescript
// src/hooks/useElectron.ts
export function useElectron() {
  const isElectron = Boolean(window.electronAPI)
  
  const openFolder = async (): Promise<string | null> => {
    if (isElectron) return window.electronAPI!.openFolder()
    // Browser fallback: show text input
    return null
  }
  
  return { isElectron, openFolder }
}
```

**Settings sections:**
1. **Model Status** — polls `/api/system/status/` every 10s
2. **Watch Directories** — native folder picker (`dialog.showOpenDialog`)
3. **About** — app version from `package.json`, backend port, userData path

**TDD Test cases:**
```
useElectron
  ✓ isElectron=true when window.electronAPI present
  ✓ openFolder calls electronAPI.openFolder()
  ✓ openFolder fallback when not in Electron

WatcherForm (Electron mode)
  ✓ "Browse…" button calls openFolder()
  ✓ selected path pre-fills input
  ✓ POST /api/watch/ on submit

SettingsPage
  ✓ model status badges color-coded
  ✓ polling re-fetches every 10s
  ✓ shows userData path in About section
```

---

### Phase 8 — Semantic Search, Documents, Chat

_(Same logic as browser plan, no Electron-specific changes)_

**Search:** `POST /api/search/` with query + k + threshold sliders  
**Documents:** `GET /api/photos/?is_doc=true` list with OCR snippets  
**Chat:** Zustand store + `POST /api/chat/` with thread_id

For all three — write tests first:
```
SearchPage:  idle → search → results → click result
DocumentsPage: fetch docs, copy OCR, empty state
ChatPage: send → receive → continue thread → reset
```

---

### Phase 9 — SSE & Job Polling

```typescript
// src/hooks/useJobPolling.ts
export function useJobPolling(photoId: number, onComplete: () => void) {
  useEffect(() => {
    const interval = setInterval(async () => {
      const base = await getBaseUrl()
      const res = await fetch(`${base}/api/job/${photoId}`)
      if (res.status === 404) {
        clearInterval(interval)
        onComplete()
      }
    }, 3000)
    return () => clearInterval(interval)
  }, [photoId])
}
```

When backend implements real SSE, swap `useJobPolling` for `useSSE` in gallery — no other changes needed.

---

### Phase 10 — Packaging

#### Backend: PyInstaller

```bash
# Bundles FastAPI + all AI models into single executable
cd backend
pyinstaller --onefile --name photo-describer-backend \
  --add-data "src:src" \
  --hidden-import easyocr \
  run.py
```

Output: `backend/dist/photo-describer-backend` → copied to `frontend/resources/backend/`

#### Frontend: Electron Builder

`electron-builder.yml`:
```yaml
appId: com.photo-describer.app
productName: Photo Describer
directories:
  output: dist-app
files:
  - dist-electron
  - dist
extraResources:
  - from: resources/backend
    to: backend
    filter: ["**/*"]
mac:
  target: dmg
  icon: resources/icon.icns
win:
  target: nsis
  icon: resources/icon.ico
```

**Full packaging workflow:**
```bash
# 1. Build Python backend
cd backend && pyinstaller ...

# 2. Build React renderer  
cd frontend && npm run build

# 3. Package everything
cd frontend && npm run dist
```

---

## Verification Plan

### Unit + Component Tests (Vitest)
```bash
cd frontend && npm run test -- --coverage
```
| Layer | Target |
|---|---|
| Electron main (ipc, protocol, backend) | 100% handlers |
| API client + base URL resolution | Electron + browser paths |
| Electron-aware hooks (useElectron) | Both contexts |
| UI atoms | All variants |
| Page components | loading/error/empty/data |

### E2E Tests (Playwright)
```bash
# Browser mode (MSW mocks)
npm run test:e2e:browser

# Electron mode (real app with MSW backend)
npm run test:e2e:electron
```

### Manual Packaging Test
```
1. npm run dist → creates Photo Describer.app
2. Open .app → Python backend starts → FastAPI ready
3. Drop 5 photos into auto-created ~/userData/photos/
4. Gallery shows them instantly
5. AI processing populates tags/description within 60s
6. Search "invoice" returns matching photos
7. Chat: "show me documents" → correct response
```

---

## Delivery Phases

| Phase | Feature | First TDD action |
|---|---|---|
| **0** | Scaffold + MSW + factories | Write 14 MSW handler tests |
| **1** | Electron main (backend spawn, protocol, IPC) | Write backend.ts tests |
| **2** | API client + image URL resolver | Write Electron vs browser URL tests |
| **3** | Design tokens + UI atoms + TitleBar | Write Button/Badge/Modal tests |
| **4** | App shell + routing + Sidebar | Write routing tests |
| **5** | Gallery page + job polling | Write PhotoCard + polling tests |
| **6** | Photo detail + native image display | Write detail + OcrPanel tests |
| **7** | Settings + native folder picker | Write useElectron hook tests |
| **8** | Search page | Write useSearch tests |
| **9** | Documents page | Write DocumentRow tests |
| **10** | Chat page | Write chatStore tests |
| **11** | SSE hook | Write useSSE + graceful degradation tests |
| **12** | Playwright E2E — browser mode | 6 flow specs |
| **13** | Playwright E2E — Electron mode | Same 6 flows in real Electron |
| **14** | PyInstaller + Electron Builder packaging | Packaging smoke test |

---

## Key Design Decisions (Updated)

| Decision | Choice | Rationale |
|---|---|---|
| Scaffold | `electron-vite` | Purpose-built for Electron + Vite, HMR works in renderer |
| Image serving | `app://` custom protocol in main | No backend endpoint needed, zero latency, works offline |
| API base URL | IPC → `getBackendPort()` | Backend port is dynamic; hardcoding breaks packaging |
| Directory picker | `dialog.showOpenDialog` via IPC | Native OS experience, no browser limitation |
| CSS | Vanilla CSS + tokens | Per project guidelines; `-webkit-app-region` for titlebar |
| State | Zustand | Same in browser and Electron, no serialization quirks |
| Titlebar | Custom on Windows, native on macOS | Platform conventions |
| CORS | Not needed in Electron | Renderer and backend are same-origin from Electron's perspective |
| DB/model path | `app.getPath('userData')` | Safe, user-writable, persists across app updates |
| Testing Electron | `electron-playwright-helpers` | Launches real Electron, full integration |
