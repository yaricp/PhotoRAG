# Photo Describer 2 — Project Summary v5

> Generated: 2026-05-10 | Commit: `70ffc03`  
> Last milestone: **Duplicates detection + Garbage/Bad Photo Detection + Frontend actions**

---

## Project Overview

**Photo Describer 2** is an AI-powered photo management system (Electron desktop app + FastAPI backend) that automatically processes photos through a multi-phase pipeline: extracting metadata, generating visual descriptions, running OCR on documents, classifying images with CLIP, detecting duplicates and low-quality photos, embedding everything into a vector database for semantic search, and translating content between languages.

**Stack:** Python 3.9 · FastAPI · SQLite + sqlite-vec · Huey (SqliteHuey) · SQLAlchemy · Pillow · NumPy · EasyOCR · CLIP (open-clip-torch) · Qwen VL · Nomic Embed · NLLB · LangGraph · Watchdog · Electron · React 18 · TypeScript · Vite · Vitest · MSW

---

## Directory Structure

```
Photo_describer2/
├── backend/
│   ├── run.py
│   ├── pyproject.toml
│   └── src/
│       ├── main.py              # FastAPI app — 435 lines
│       ├── models.py            # ORM models — 229 lines
│       ├── db_service.py        # All CRUD — 729 lines
│       ├── schemas.py           # Pydantic schemas — 170 lines
│       ├── quality_checks.py    # ★ NEW — 7 pure detection functions — 88 lines
│       ├── install.py           # Model pre-download — 387 lines
│       ├── utils.py             # Helpers, EXIF, hashing — 196 lines
│       ├── config.py            # Pydantic Settings — 95 lines
│       ├── database.py          # Engine, SessionLocal
│       ├── deps.py              # FastAPI DI
│       ├── geo.py               # Reverse geocoding — 102 lines
│       ├── metadata.py          # EXIF parsing
│       ├── observer.py          # Watchdog event handler
│       ├── watcher_service.py   # Watcher lifecycle
│       ├── vector_db_services.py # sqlite-vec — 133 lines
│       ├── ai/
│       │   ├── registry.py      # AIModelRegistry singleton — 296 lines
│       │   ├── clip.py          # ClipTagger — 273 lines
│       │   ├── vision.py        # Qwen VL — 104 lines
│       │   ├── ocr.py           # EasyOCR singleton
│       │   ├── translator.py    # NLLB — 90 lines
│       │   └── prompts.py       # Prompt templates
│       ├── queues/
│       │   ├── clip_queue.py
│       │   ├── vision_queue.py
│       │   ├── embedding_queue.py
│       │   └── translation_queue.py
│       └── tasks/
│           ├── __init__.py      # start_pipeline()
│           ├── utils.py         # phase_logic, _dispatch_tasks — 194 lines
│           ├── clip_tasks.py    # metadata + CLIP tasks — 268 lines
│           ├── quality_tasks.py # ★ NEW — brightness/edge/blur/entropy/screenshot — 88 lines
│           ├── vision_tasks.py  # vision + OCR tasks — 150 lines
│           ├── embedding_tasks.py # embedding tasks — 152 lines
│           ├── translation_tasks.py
│           └── folder_scanners.py — 88 lines
├── backend/tests/
│   ├── test_quality_checks.py   # ★ NEW — 17 tests — 177 lines
│   ├── test_quality_tasks.py    # ★ NEW — 9 tests — 290 lines
│   ├── test_models_quality.py   # ★ NEW — 9 tests — 145 lines
│   ├── test_api_garbage.py      # ★ NEW — 4 tests — 94 lines
│   ├── test_api_duplicates.py   # 5 tests — 151 lines
│   ├── test_pipeline_perceptual.py  # 218 lines
│   ├── test_pipeline_exact_duplicate.py  # 183 lines
│   ├── test_db_service_duplicates.py  # 208 lines
│   ├── test_models_duplicates.py  # 172 lines
│   ├── test_geoposition.py      # 131 lines
│   ├── test_main.py             # 162 lines
│   ├── test_e2e_pipeline.py     # 145 lines
│   └── ... (20+ more test files)
├── frontend/src/
│   ├── pages/
│   │   ├── GalleryPage.tsx      # ★ Updated — Archive/Delete per card — 175 lines
│   │   ├── DuplicatesPage.tsx   # 237 lines
│   │   ├── GarbageBadPhotoPage.tsx  # ★ NEW — 150 lines
│   │   ├── GarbageBadPhotoPage.css  # ★ NEW
│   │   ├── AppRoutes.tsx        # ★ Updated — /garbage route — 30 lines
│   │   └── ...
│   ├── components/
│   │   ├── photos/PhotoCard.tsx # ★ Updated — optional onArchive/onDelete
│   │   ├── photos/PhotoCard.css # ★ Updated — action button styles
│   │   └── ui/Sidebar.tsx       # ★ Updated — Garbage nav link
│   └── api/client.ts            # ★ Updated — getGarbageSummary, getGarbagePhotos
├── planning/
│   ├── task_garbage_detection.md  # ★ NEW — 11-task implementation plan
│   └── ...
└── results/
    └── summary_v5.md            # ← this file
```

---

## Processing Pipeline (3 Phases) — Updated

```
Phase 1 (init → first):
  metadata_task          — EXIF, geo, camera + ★ thumbnail + no_exif quality checks
  auto_tag_clip_task     — CLIP tags
  categorize_photo_task  — CLIP categories
  vision_task            — Qwen VL description
  ocr_task               — EasyOCR text
  compute_perceptual_hashes_task — pHash for dedup
  ★ brightness_task      — NEW: flag too dark / overexposed
  ★ edge_density_task    — NEW: flag featureless/flat images
  ★ blur_task            — NEW: flag blurry images (Laplacian)
  ★ entropy_task         — NEW: flag low-information images

Phase 2 (first → second):
  final_embedding_task
  translate_description_task
  is_this_document_task

Phase 3 (second → third):
  embedding_document_text_task
  ★ screenshot_detect_task  — NEW: flag UI screenshots
```

---

## New Features Since v4

### Duplicates Detection (Phase before v5)

- **`PhotoDuplicate` ORM model** — tracks exact (hash) and perceptual (pHash distance) duplicate pairs
- **`compute_perceptual_hashes_task`** — computes pHash in phase 1, records duplicates
- **`GET /api/duplicates/`** — returns grouped exact + perceptual duplicate pairs
- **`DELETE /api/duplicates/{record_id}`** — removes duplicate record + deletes file from disk
- **`POST /api/photos/{id}/archive`** — marks photo as archived
- **`DuplicatesPage`** — frontend page with exact duplicate checkboxes and perceptual duplicate cards

### Garbage / Bad Photo Detection (v5)

#### Backend

**New table: `photo_quality_issues`**

```sql
CREATE TABLE photo_quality_issues (
    id         INTEGER PRIMARY KEY,
    photo_id   INTEGER NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
    issue_type TEXT NOT NULL,   -- thumbnail | no_exif | brightness | edge_density | blur | entropy | screenshot
    score      REAL,
    detected_at DATETIME DEFAULT now
);
```

**`quality_checks.py`** — 7 pure detection functions (no DB, no side effects):

| Function | Technique | Threshold | Normalization |
|---|---|---|---|
| `check_resolution` | pixel count | < 10,000 px | — |
| `check_exif` | EXIF key presence | no camera + no date | — |
| `check_brightness` | mean luminance | < 30 or > 220 | — |
| `check_edge_density` | FIND_EDGES filter | < 2% edge pixels | resize 512×512 |
| `check_blur` | Laplacian variance | < 100 | resize 512×512 |
| `check_entropy` | median patch entropy | < 3.0 bits | resize 512×512, GaussianBlur(r=2) |
| `check_screenshot` | top-10 colors in 64-color quantization | > 45% pixels | resize 256×256 |

**`quality_tasks.py`** — 5 Huey tasks on `clip_queue`:
`brightness_task`, `edge_density_task`, `blur_task`, `entropy_task`, `screenshot_detect_task`

**New API endpoints:**

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/garbage/` | Count of flagged photos per issue type |
| `GET` | `/api/garbage/{issue_type}/photos/` | Paginated photos for a given issue type |

#### Frontend

- **`GarbageBadPhotoPage`** — 4 sections: Technical Garbage (7 expandable rows with live counts), Semantic / Temporary / Subjective (placeholders)
- **`PhotoCard`** — optional `onArchive` / `onDelete` props; buttons rendered only when handlers passed
- **`GalleryPage`** — Archive + Delete buttons on every card with optimistic removal
- **`/garbage` route** and **Garbage sidebar link**

---

## API Endpoints (Full List)

| Method | Path | Tag | Description |
|---|---|---|---|
| `GET` | `/api/system/status/` | System | Model states |
| `POST` | `/api/watchers/` | Watchers | Start directory watcher |
| `GET` | `/api/watchers/` | Watchers | List active watchers |
| `DELETE` | `/api/watchers/{id}` | Watchers | Stop watcher |
| `GET` | `/api/photos/` | Photos | Paginated list (filter/sort) |
| `GET` | `/api/photos/{id}` | Photos | Single photo |
| `DELETE` | `/api/photos/{id}` | Photos | Delete photo + file |
| `POST` | `/api/photos/{id}/archive` | Photos | Archive photo |
| `GET` | `/api/photos/available-dates/` | Photos | Calendar dates |
| `GET` | `/api/duplicates/` | Photos | Exact + perceptual groups |
| `DELETE` | `/api/duplicates/{record_id}` | Photos | Remove duplicate record + file |
| `GET` | `/api/garbage/` | Garbage | Issue type counts |
| `GET` | `/api/garbage/{issue_type}/photos/` | Garbage | Paginated flagged photos |
| `POST` | `/api/search/` | Photos | Semantic vector search |
| `GET` | `/api/tags/` | Metadata | All tags |
| `GET` | `/api/categories/` | Metadata | All categories |
| `GET` | `/api/cameras/` | Metadata | All cameras |
| `GET` | `/api/geopositions/` | Metadata | All geopositions |
| `GET` | `/api/models/` | Models | AI model configs |
| `PUT` | `/api/models/{type}` | Models | Update + reload model config |
| `POST` | `/api/chat/` | Agent | Chat with AI agent |
| `GET` | `/api/jobs/` | Jobs | All processing jobs |
| `GET` | `/api/jobs/{photo_id}` | Jobs | Job status for photo |
| `GET` | `/api/folder_scanners/progress/` | Folder Scanners | Scan progress |
| `POST` | `/api/folder_scanners/` | Folder Scanners | Start folder scan |
| `DELETE` | `/api/folder_scanners/{id}` | Folder Scanners | Remove scanner |

---

## Database Models (`src/models.py`)

| Model | Key Fields | Notes |
|---|---|---|
| `Photo` | `file_path`, `hash`, `description`, `translated_description`, `ocr_text`, `is_doc`, `captured_at`, `is_archived` | Core entity |
| `Tag` / `PhotoTag` | `name`, `score` | Many-to-many via junction |
| `Category` / `PhotoCategory` | `name`, `prompt`, `score` | |
| `Camera` | `make`, `model`, `lens` | |
| `Geoposition` | `lat`, `lon`, `address` | Deduplicated, rounded to 3dp |
| `ModelState` | `name`, `status` | |
| `Watcher` | `path`, `destination_path` | |
| `ProcessingJob` | `photo_id`, `phase`, `tasks` | Comma-separated task names |
| `FolderScanner` | `path`, `scanned_steps`, `total_steps` | |
| `AIModelConfig` | `config_type`, `model_id`, `enabled` | |
| `PhotoHash` | `photo_id`, `phash` | Perceptual hash |
| `PhotoDuplicate` | `original_photo_id`, `duplicate_photo_id`, `match_type`, `hash_distance` | exact or perceptual |
| `PhotoQualityIssue` | `photo_id`, `issue_type`, `score`, `detected_at` | ★ NEW — one row per flag |

---

## Test Suite

**Backend:** 39 new tests (garbage detection) + existing suite

| File | Tests | Focus |
|---|---|---|
| `test_quality_checks.py` | 17 | Pure detection functions |
| `test_quality_tasks.py` | 9 | Huey task dispatch + pipeline wiring |
| `test_models_quality.py` | 9 | ORM model + cascade + DB service |
| `test_api_garbage.py` | 4 | REST endpoints |
| `test_api_duplicates.py` | 5 | Duplicate endpoints |
| `test_pipeline_perceptual.py` | — | pHash pipeline |
| `test_pipeline_exact_duplicate.py` | — | Exact duplicate pipeline |
| … | … | |

**Frontend:** 114 passing tests (Vitest + MSW)

| File | Tests | Focus |
|---|---|---|
| `PhotoCard.test.tsx` | 12 | Card rendering + action buttons |
| `GarbageBadPhotoPage.test.tsx` | 5 | Page sections, expand, optimistic removal |
| `client.test.ts` (garbage) | 2 | `getGarbageSummary`, `getGarbagePhotos` |
| `Sidebar.test.tsx` | includes garbage link | Nav integration |

---

## Key Source Files by Size

| File | Lines | Role |
|---|---|---|
| `src/db_service.py` | 729 | All CRUD + quality + duplicate helpers |
| `src/main.py` | 435 | FastAPI app + all endpoints |
| `src/install.py` | 387 | Model pre-download + DB migrations |
| `src/ai/registry.py` | 296 | AI model singleton management |
| `src/tasks/clip_tasks.py` | 268 | Metadata + CLIP + quality checks in phase 1 |
| `src/ai/clip.py` | 273 | CLIP tagging + categorization |
| `src/models.py` | 229 | All SQLAlchemy ORM models |
| `src/utils.py` | 196 | Helpers, EXIF extraction |
| `src/tasks/utils.py` | 194 | Pipeline phase orchestration |
| `src/schemas.py` | 170 | Pydantic schemas |
| `src/tasks/embedding_tasks.py` | 152 | Embedding tasks |
| `src/tasks/vision_tasks.py` | 150 | Vision + OCR tasks |
| `src/quality_checks.py` | 88 | Pure quality detection functions |
| `src/tasks/quality_tasks.py` | 88 | Quality Huey tasks |

---

## Git History (Since v4)

| Hash | Message |
|---|---|
| `70ffc03` | feat: add /garbage route and sidebar link for GarbageBadPhotoPage |
| `8c9d1a5` | feat: add GarbageBadPhotoPage with expandable technical issue sections |
| `5015dd0` | feat: add getGarbageSummary and getGarbagePhotos API client functions |
| `a9709a7` | feat: add optional onArchive/onDelete action buttons to PhotoCard |
| `8f10181` | feat: add /api/garbage/ summary and photo-list endpoints |
| `d35b19c` | feat: add quality detection tasks and wire into pipeline phases 1 and 3 |
| `33a5d70` | feat: add pure quality detection functions with tests |
| `1a2498d` | test: add distinct dedup test and fix review nits |
| `9978a74` | feat: add quality issue DB service functions |
| `b348989` | test: add nullable score test; fix trailing newline in models.py |
| `93c2d08` | feat: add PhotoQualityIssue ORM model with cascade delete |
| `12aae85` | feat: add Duplicates feature with perceptual hashing and dedup detection |

---

## Known Open Issues

1. **E2E test `is_doc` assertion** — `is_this_document_task` moved to phase second; mock fixture still references phase-1 behavior.
2. **`nomic_embedder.name` NoneType** — class-level patch vs. instance-level causes getter to fire during E2E setup.
3. **23 pre-existing frontend test failures** — `GalleryPage`, `PhotoDetailPage`, `routing` tests fail due to unrelated MSW handler gaps; not caused by v5 changes.
4. **Quality checks run only on new photos** — existing photos in DB are not retroactively scanned; a bulk-scan endpoint is not yet implemented.

---

## Next Steps

- [ ] Retroactive bulk quality scan for existing photos
- [ ] Semantic / Temporary / Subjective garbage detection (currently placeholder sections)
- [ ] Fix pre-existing frontend test failures (GalleryPage, PhotoDetailPage, routing)
- [ ] Fix E2E pipeline test assertions for 3-phase structure
- [ ] Archive view — dedicated page showing all archived photos
