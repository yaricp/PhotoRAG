# PhotoRAG — Project Summary v6

> **Generated:** 2026-05-19 | **Commit:** `b2bc7f4` | **Branch:** `feature/macos-installer`
> **Last milestones:** Model-config wizard step · Translation fixes · Embedding auto-rebuild · Windows installer plan + implementation

---

## 1. What Is PhotoRAG?

PhotoRAG is a self-hosted, **cross-platform desktop application** for AI-powered photo management. It runs entirely offline (with optional remote API fallback), enriches photos with machine-generated descriptions, tags, OCR text, and vector embeddings, then exposes them through semantic search and a conversational AI agent.

**Rename:** the project was originally called *Photo Describer 2* and was renamed to **PhotoRAG** in commit `44c1688`.

---

## 2. Tech Stack

| Layer | Technology |
|---|---|
| Desktop shell | Electron 31 + electron-vite |
| Frontend | React 18, TypeScript, Zustand, React Router 6 |
| Backend | Python 3.13, FastAPI, Uvicorn |
| ORM / DB | SQLAlchemy + SQLite (main), sqlite-vec (vector search) |
| Async tasks | Huey 2.5.0 (SQLite backend, 6 worker processes) |
| AI orchestration | LangChain, LangGraph |
| Vision | Qwen2-VL-2B (local) or OpenAI/Anthropic/Google (remote) |
| Tagging/Search | OpenCLIP ViT-B-32 (local) |
| Embeddings | nomic-embed-text v1.5 (local) or OpenAI text-embedding-3-small (remote) |
| Translation | NLLB-200-distilled-600M (local) or OpenAI/Anthropic (remote) |
| OCR | Tesseract / EasyOCR (local) or remote vision models |
| Chat | LangGraph ReAct agent with 30+ tools |
| Packaging | electron-builder → macOS universal DMG + Windows x64 NSIS |
| Build Python | python-build-standalone 3.13.13+20260510 |
| Testing | Vitest (frontend), Pytest (backend), Playwright (e2e), MSW (mocks) |

---

## 3. Architecture Overview

```
┌────────────────────────────────────────────────────┐
│  Electron Main Process                             │
│  index.ts → backend.ts (spawn Python)             │
│          → ipc.ts    (setup wizard IPC)           │
│          → protocol.ts (file:// serving)          │
└────────────┬───────────────────────────────────────┘
             │ HTTP on 127.0.0.1:<dynamic port>
┌────────────▼───────────────────────────────────────┐
│  FastAPI Backend (run.py → src/main.py)           │
│  ├── REST API (40+ endpoints)                     │
│  ├── Incoming pipeline (4 phases)                 │
│  ├── 6 Huey worker processes (one per queue)      │
│  ├── Watchdog filesystem observer                 │
│  └── LangGraph AI agent (30+ tools)              │
└────────────┬───────────────────────────────────────┘
             │
┌────────────▼───────────────────────────────────────┐
│  SQLite Databases (APP_DATA_DIR)                  │
│  db.sqlite3        – photos, tags, categories,    │
│                      models, settings, history    │
│  task_results.db   – Huey task results            │
│  clip/vision/embedding/ocr/…sqlite3 – queues      │
│  (sqlite-vec table inside db.sqlite3)             │
└────────────────────────────────────────────────────┘
```

### Photo Processing Pipeline (4 phases)

```
New photo detected (watchdog or folder scan)
    │
    Phase 0 [CPU, parallel]:
    ├── metadata extraction (EXIF, GPS, camera)
    ├── perceptual hashes (dHash / pHash / aHash)
    └── quality checks (resolution, EXIF completeness)
    │
    Phase 1 [AI, parallel]:
    ├── CLIP tagging + auto-categorization
    ├── vision description (Qwen2-VL-2B or remote)
    ├── OCR text extraction
    ├── brightness / edge density / blur / entropy scoring
    └── duplicate detection (hash collision)
    │
    Phase 2 [AI, parallel]:
    ├── is_document classification
    ├── translation (description → user language)
    └── vector embedding (for semantic search)
    │
    Phase 3 [sequential]:
    ├── document embedding
    └── screenshot detection
```

---

## 4. Feature Inventory

### 4.1 Photo Management
- CRUD operations for photos (list, detail, update, delete)
- Manual tag and category linking / unlinking from the photo detail view
- `is_doc` / `is_trash` flag toggling
- Description and OCR text inline editing
- Action history with undo (create_folder, move, archive, tag/category operations)

### 4.2 AI Enrichment Pipeline
- **Vision model**: Qwen2-VL-2B generates natural-language descriptions (local or remote)
- **CLIP tagging**: ViT-B-32 matches photos against a vocabulary of template tags & categories
- **OCR**: Tesseract/EasyOCR extracts printed text; embedded separately for doc search
- **Translation**: NLLB-200 translates descriptions to the user's preferred language (default: Russian/English configurable)
- **Embeddings**: nomic-embed-text v1.5 or OpenAI text-embedding-3-small, stored in sqlite-vec VSS table

### 4.3 Semantic Search
- Vector similarity search via sqlite-vec
- Non-English queries are translated to English before embedding lookup
- Language read from DB (`get_setting`) not from env var — respects user's SettingsPage selection
- Threshold and top-K configurable

### 4.4 Filtering & Browsing
- Gallery with pagination (configurable page size)
- Multi-select filters: tags, categories, cameras, geopositions
- Date filter: cascading year → month → day modals
- All filters combinable; available dates update dynamically based on active filters

### 4.5 Duplicate Detection
- **Exact duplicates**: SHA-256 hash collision
- **Near-duplicates**: perceptual hash (dHash) with Hamming distance ≤ 10
- Grouped by "original" (earliest `captured_at`); duplicates listed per group
- Delete duplicate record endpoint

### 4.6 Quality / Garbage Detection
- 7 quality checks: thumbnail size, missing EXIF, brightness outlier, edge density, blur (Laplacian), entropy, screenshot detection
- `GET /api/garbage/` returns per-issue counts
- `GET /api/garbage/{issue_type}/photos/` returns paginated photos for each issue type
- Unmark-as-garbage endpoint

### 4.7 AI Agent Chat
- LangGraph ReAct agent with persistent conversation threads
- 30+ tools: semantic search, metadata filters, photo CRUD, tagging, archiving, undo, quality checks, duplicate comparison, geocoding, folder management
- Context-aware: agent can reference photos already on screen

### 4.8 Folder Watching & Scanning
- Watchdog-based real-time observer for configured watch folders
- Folder scanner for one-shot batch import of existing photos
- Progress tracked in `folder_scanners` table, streamed to frontend

### 4.9 Template Tags & Categories
- User-managed CLIP vocabulary (name + CLIP prompt text)
- Changes trigger background CLIP feature recompute for all templates
- Full CRUD with paginated list views

### 4.10 Model Configuration
- All 6 AI models (vision, clip, embedding, translator, ocr, chat) configurable as **local** or **remote**
- Per-model settings: provider, model name, URL, API key, similarity limit
- Stored in `ai_model_configs` table; read at worker startup
- ModelsPage in settings shows current download/loading/ready/error state
- **PipelineWarningBanner**: shown in the app header when any required model is in `error` state (loading/pending states suppressed to avoid false positives)
- **EmbeddingReindexBanner**: shown when the embedding model was changed and photos lack updated vectors; dismissable per session

### 4.11 Prompt Management
- All AI prompts stored in the `prompts` DB table (no hardcoded JSON)
- PromptsPage lets users edit vision, translation, chat system prompts
- Fresh DB read on every pipeline invocation (no caching)

### 4.12 Settings
- Default language (drives translation target + search query translation)
- Language preference read from `app_settings` DB via `get_setting()` — not from env vars
- Additional per-model API keys and remote URLs

---

## 5. Embedding Dimension Auto-Rebuild

When the embedding model changes (e.g., local 768-dim → OpenAI 1536-dim):

1. **Startup lifespan**: compares current VSS table dimension against configured model's dimension; calls `rebuild_embeddings_vss(db, new_dim)` if they differ
2. **`save_embedding`**: catches `"Dimension mismatch"` errors at write time and auto-recovers with a rebuild + retry
3. **`/api/system/reindex-status/`**: returns `{ needed, total, indexed }` — used by `EmbeddingReindexBanner` to tell the user how many photos need re-indexing

---

## 6. First-Run Setup Wizard

7-step wizard runs before the backend starts (IPC handlers bypass FastAPI entirely):

| Step | Description |
|---|---|
| Welcome | App introduction, system requirements |
| Install Deps | Creates `userData/venv/`, runs `pip install -r requirements.txt` (with `--extra-index-url` for CPU-only PyTorch on Windows) |
| Init DB | Runs `init_db_only.py` via venv Python to create all SQLite tables |
| Model Config | User sets local/remote mode, provider, API key, model name for each AI model |
| Downloading | Downloads selected local models one at a time with tqdm-patched progress |
| Done | Writes `setup_done`, starts backend, calls `waitForBackend()` |

The **model-config step** replaced the old "model picker" (checkboxes) step — it goes directly from configuration to downloading selected local models, skipping the redundant picker screen.

---

## 7. Cross-Platform Packaging

### macOS (implemented, shipping)
- **Format**: Universal DMG (arm64 + x86_64 via `lipo`)
- **Python**: python-build-standalone 3.13.13, universal binary in `resources/python/`
- **Python path**: `resources/python/bin/python3`
- **Venv path**: `~/Library/Application Support/PhotoRAG/venv/bin/python3`
- **Data dir**: `~/Library/Application Support/PhotoRAG/`
- **Build**: `bash scripts/build-mac.sh` or `npm run dist:mac`
- **CI**: `.github/workflows/build-mac.yml` on `macos-latest`
- **Code signing**: not yet wired (stub notarize.js)

### Windows (implemented, to be tested)
- **Format**: NSIS x64 `.exe` installer
- **Python**: python-build-standalone 3.13.13 x64 (`install_only`, `.tar.gz`)  
  Filename: `cpython-3.13.13+20260510-x86_64-pc-windows-msvc-install_only.tar.gz`
- **Python path**: `resources/python/python.exe`
- **Venv path**: `%APPDATA%\PhotoRAG\venv\Scripts\python.exe`
- **Data dir**: `%APPDATA%\PhotoRAG\`
- **Process kill**: `taskkill /F /T /PID <pid>` (replaces Unix `kill(-pid)`)
- **Spawn**: `windowsHide: true` to suppress console windows
- **PyTorch**: `--extra-index-url https://download.pytorch.org/whl/cpu` to avoid 2.5 GB CUDA wheel
- **Build**: `bash scripts/build-win.sh` (macOS/Linux cross-compile) or `scripts/build-win.ps1` (native Windows)
- **CI**: `.github/workflows/build-win.yml` on `windows-latest`
- **Code signing**: placeholder env vars (`WIN_CSC_LINK`, `WIN_CSC_KEY_PASSWORD`) ready for certificate

### Platform-Aware Path Resolution
All platform differences are centralized:
- `backend.ts`: `locatePython()`, `locateVenvPython()` with `process.platform === 'win32'` guards
- `ipc.ts`: `venvBin(venvPath, name)` helper replaces all hardcoded `bin/pip`, `bin/python3`
- `data_dir.py`: `win32` branch uses `%APPDATA%`

---

## 8. Key Architectural Decisions

| Decision | Rationale |
|---|---|
| SQLite over PostgreSQL | Simpler deployment; no server required for local desktop use; sqlite-vec handles vector search |
| Huey over Celery/RQ | SQLite-backed; no Redis required; 6 isolated worker processes (one per model type) |
| Bundled Python (python-build-standalone) | User needs zero Python knowledge; no system Python dependency |
| Venv in `userData/venv/` (not in bundle) | Bundle stays read-only; pip packages installed once at setup time |
| `get_setting(db)` over `Main_Settings()` | Pydantic BaseSettings reads env vars at startup only — user preferences saved to DB are invisible to it |
| DB-driven model configs | Allows model switching from the UI without touching `.env` files or restarting the process |
| DB-driven prompts | Users can customize AI behavior without editing code |
| `rebuild_embeddings_vss` on dimension change | sqlite-vec VSS table has a fixed dimension — must be recreated when the embedding model changes |
| No authentication | Single-user local app; authentication adds complexity with no benefit |

---

## 9. File Structure (Key Files)

```
Photo_describer2/
├── backend/
│   ├── run.py                        entry point (dev)
│   ├── init_db_only.py               DB-only init (used by wizard IPC)
│   ├── requirements.txt
│   └── src/
│       ├── main.py                   FastAPI app + all REST endpoints
│       ├── models.py                 SQLAlchemy ORM (40+ tables)
│       ├── db_service.py             CRUD + query layer (100+ functions)
│       ├── schemas.py                Pydantic request/response schemas
│       ├── config.py                 Pydantic BaseSettings (env-driven)
│       ├── data_dir.py               Platform-aware APP_DATA_DIR resolver
│       ├── incoming_pipeline.py      4-phase pipeline orchestrator
│       ├── model_services.py         Model invocation (local + remote)
│       ├── vector_db_services.py     sqlite-vec read/write + dimension rebuild
│       ├── quality_checks.py         7 photo quality detectors
│       ├── ai/
│       │   ├── registry.py           Thread-safe model singleton loader
│       │   ├── vision.py / clip.py / translator.py / ocr.py
│       │   └── *_remote.py           Remote API variants
│       ├── queues/                   Huey queue definitions (6 queues)
│       ├── tasks/                    Task implementations
│       └── graphs/
│           ├── ai_agent.py           LangGraph ReAct agent
│           └── tools.py              30+ agent tools (60 KB)
├── frontend/
│   ├── electron/
│   │   ├── main/
│   │   │   ├── index.ts              Electron lifecycle
│   │   │   ├── backend.ts            Python spawn + port discovery
│   │   │   └── ipc.ts               All IPC handlers (setup wizard)
│   │   └── preload/index.ts          Context bridge
│   ├── resources/
│   │   ├── icon.icns / icon.ico      App icons
│   │   ├── dmg-background.png
│   │   └── python/                   Bundled Python runtime
│   └── src/
│       ├── App.tsx                   Root (banners + layout)
│       ├── api/client.ts             40+ API wrappers
│       ├── pages/
│       │   ├── GalleryPage.tsx
│       │   ├── SearchPage.tsx
│       │   ├── ChatPage.tsx
│       │   ├── DuplicatesPage.tsx
│       │   ├── GarbageBadPhotoPage.tsx
│       │   ├── ModelsPage.tsx
│       │   ├── PromptsPage.tsx
│       │   └── SetupWizard/          7-step first-run wizard
│       └── components/ui/
│           ├── PipelineWarningBanner.tsx
│           ├── EmbeddingReindexBanner.tsx
│           └── TesseractBanner.tsx
├── scripts/
│   ├── download-python.sh            macOS Python download
│   ├── download-python-win.sh        Windows Python download (.tar.gz)
│   ├── download-python-win.ps1       PowerShell variant
│   ├── build-mac.sh / build-win.sh   Build orchestration
│   ├── build-win.ps1                 PowerShell build
│   ├── make-icns.sh / make-ico.sh    Icon generation
│   └── test-bundle-*.sh              Bundle verification
├── .github/workflows/
│   ├── build-mac.yml                 CI: macOS DMG
│   └── build-win.yml                 CI: Windows NSIS
└── planning/                         44 implementation plan files
```

---

## 10. API Surface (Major Groups)

| Group | Endpoints |
|---|---|
| Photos | GET /api/photos/ · GET /api/photos/{id} · PUT /api/photos/{id} · DELETE · PUT flags · POST reindex · POST run-pipeline · POST /archive |
| Photo metadata | GET available-dates · GET/POST/DELETE tags · GET/POST/DELETE categories |
| Search | POST /api/search/ (semantic vector) |
| Chat | POST /api/chat/ · GET history |
| Jobs | GET /api/jobs/ · GET /api/jobs/{id} |
| Pipeline | GET active · GET recent · GET /photos/{id}/pipeline |
| Models | GET /api/models/ · PUT /api/models/{type} |
| Settings | GET /api/settings/ · PUT /api/settings/{key} |
| Prompts | GET /api/prompts/ · PUT /api/prompts/{key} |
| Tags | GET /api/tags/ |
| Categories | GET /api/categories/ |
| Cameras | GET /api/cameras/ |
| Geopositions | GET /api/geopositions/ |
| Template Tags | GET/POST/PUT/DELETE /api/template-tags/ |
| Template Categories | GET/POST/PUT/DELETE /api/template-categories/ |
| Duplicates | GET /api/duplicates/ · DELETE /api/duplicates/{id} |
| Garbage | GET /api/garbage/ · GET /api/garbage/{type}/photos/ · DELETE /api/garbage/{photo_id}/issues |
| History | GET /api/history/ · POST /api/history/undo/ |
| Watchers | GET/POST/DELETE /api/watchers/ |
| Folder Scanners | GET/POST /api/folder_scanners/ · DELETE /api/scanners/{id} |
| System | GET /api/system/status/ · GET /api/system/tesseract/ · GET /api/system/reindex-status/ |

---

## 11. Remaining Work / Known Gaps

| Area | Status | Notes |
|---|---|---|
| Windows build — end-to-end test | **Not yet tested** | Needs a real Windows VM or CI run |
| macOS code signing / notarization | Stub only | `scripts/notarize.js` is empty; needs Apple Developer account + secrets |
| Windows code signing | Placeholder | `WIN_CSC_LINK` / `WIN_CSC_KEY_PASSWORD` env vars ready but no cert yet |
| ARM64 Windows | Out of scope (Phase 2) | Snapdragon X / Copilot+ support deferred |
| Linux packaging | Not planned | App data dir resolves correctly; no AppImage/deb build configured |
| Agent tools expansion (14 new tools) | Planned | `phase11_reindex_and_pipeline_tools.md` lists full list |
| Tesseract auto-install | Detection only | Banner shown if missing; no automated install |
| Full E2E test suite | Partial | `test-integration.sh` exists; Playwright tests exist but limited coverage |
| CUDA / GPU support on Windows | Not planned | CPU-only PyTorch; GPU inference not in scope |

---

## 12. Development Workflow

```bash
# Backend (dev)
cd backend
python run.py

# Frontend + Electron (dev)
cd frontend
npm run dev

# Build macOS DMG
bash scripts/build-mac.sh        # downloads Python, builds, outputs dist-electron/*.dmg

# Build Windows NSIS installer
bash scripts/build-win.sh        # cross-compiles from macOS; or run on Windows
# or natively on Windows:
powershell -ExecutionPolicy Bypass -File scripts/build-win.ps1

# Run tests
cd frontend && npm test          # Vitest unit tests
cd backend && pytest             # Python unit + integration tests
```

---

*Generated by Claude Sonnet 4.6 on 2026-05-19 from 44 planning documents and full codebase survey.*
