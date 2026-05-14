# Huey Queue Reconfiguration Plan (v2)

## Goal

Isolate every AI model into its own Huey worker process so the main FastAPI process
**never loads any model into memory**. All model calls from the pipeline, API endpoints,
and AI agent tools go through async `model_services.py` functions that either:
- submit a Huey task to the model's worker process and poll `task_results.db` for the result, OR
- make an HTTP request to a remote API.

This saves RAM by ensuring each model occupies memory only in its dedicated worker process.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│  FastAPI process                                             │
│  main.py · graphs/tools.py · incoming_pipeline.py           │
│  ─────────────────────────────────────────────────────────   │
│  model_services.py  (async call_X_model functions)          │
│    local → Huey task + poll task_results.db                  │
│    remote → HTTP via httpx                                   │
└──────────────────┬───────────────────────────────────────────┘
                   │ Huey tasks submitted via SqliteHuey queues
    ┌──────────────┼──────────────┬──────────────┬────────────┐
    │              │              │              │            │
┌───▼───┐   ┌──────▼─────┐ ┌────▼────┐ ┌───────▼──┐ ┌──────▼─────┐
│clip   │   │vision      │ │embedding│ │ocr       │ │translation │
│worker │   │worker      │ │worker   │ │worker    │ │worker      │
│thread │   │thread      │ │thread   │ │thread    │ │thread      │
└───┬───┘   └──────┬─────┘ └────┬────┘ └───────┬──┘ └──────┬─────┘
    │              │              │              │            │
    └──────────────┴──────────────┴──────────────┴────────────┘
                          task_results.db
                    (shared SQLite, one row per call)
```

**What each layer does:**

| Layer | Responsibility |
|---|---|
| Queue worker tasks (`queues/*.py`) | Run the model. Save result to `task_results.db`. No main DB access. |
| `model_services.py` | Async gateway: local → Huey task + poll; remote → HTTP. |
| `tasks/*.py` | Async pipeline steps: read photo from main DB, call `model_services`, write results to main DB. |
| `incoming_pipeline.py` | Orchestrates pipeline phases with `asyncio.gather`. |
| `graphs/tools.py` | Async LangChain tools: call `model_services` for model work. |
| `main.py` endpoints | Never touch models. Search uses pre-computed embeddings only. |

---

## Current State Audit

### Already done (partial implementation exists)

| File | Status |
|---|---|
| `config.py` | ✅ Split into per-model settings classes |
| `db/task_results.py` | ✅ `save_result`, `get_result`, `init_db` exist |
| `model_services.py` | ✅ `call_clip_model`, `call_embedding_model`, `call_translation_model` (async) |
| `queues/clip_queue.py` | ✅ `call_local_clip_model` task with `save_result` |
| `queues/embedding_queue.py` | ✅ `call_local_embedding_model` task |
| `queues/translation_queue.py` | ⚠️ Has task but syntax error on line 2 (`import` without module) |
| `queues/vision_queue.py` | ❌ Still old pattern — no `call_local_vision_model` task |
| `observer.py` | ✅ Calls async pipeline via `asyncio.run_coroutine_threadsafe` |

### Broken / needs fix now

| File | Problem |
|---|---|
| `translation_queue.py` line 2 | `import` statement with nothing after it — syntax error |
| `incoming_pipeline.py` line 4 | `async start_pipeline` without `def` — syntax error |
| `graphs/ingestion.py` | Old LangGraph prototype — loads models directly; should be deleted |
| `main.py` line 365 | `translator: Optional[Translator] = Depends(get_translator)` in search endpoint — loads Translator in API process |
| `main.py` line 369 | `get_photos_by_vector(db, request.text_query, ...)` — calls embedding model inside API process |
| `main.py` line 678 | `final_embedding_task(photo_id, phase="edit")` — old Huey task call, bypasses model_services |
| `graphs/tools.py` lines 663–664 | `describe_photo` calls `registry.generate_vision_text()` directly |
| `graphs/tools.py` lines 863–870 | `estimate_photo_quality_deep` calls `registry.clip_tagger.model.encode_image()` directly |
| `graphs/tools.py` lines 1022–1024 | `compare_photos_deep` calls `registry.clip_tagger.model.encode_image()` directly |
| `tasks/clip_tasks.py` | All tasks use `registry.clip_tagger` directly |
| `tasks/vision_tasks.py` | All tasks use `registry.generate_vision_text()` directly |
| `tasks/embedding_tasks.py` | All tasks use `registry.embedder_encode_text()` directly |
| `tasks/translation_tasks.py` | Task uses `registry.translator.translate()` directly |
| `tasks/quality_tasks.py` | Still registered on `clip_queue` as Huey tasks (no DB calls but wrong pattern) |

---

## Part 1 — Per-Queue Thread-Safe Model Registries

Each queue file manages its own model singleton in-process, with a `threading.Lock` for
thread-safe inference. This replaces usage of the global `AIModelRegistry` in worker
processes.

### Model name comes from the main DB

The user can change which local model to use on the **ModelPage** frontend. That change
is written to `ai_model_configs` table in `db.sqlite3`. Each worker reads this table
**once at startup** (inside `_get_model()`) to discover the current model name.

**Download behavior:**
- `from_pretrained()` (HuggingFace, sentence-transformers, etc.) auto-downloads the
  model to the local HuggingFace cache (`~/.cache/huggingface/hub/`) on first use.
- If the model name in the DB changed since the last run, the next startup downloads
  the new model. The old cached files remain on disk (manual cleanup or future housekeeping).
- **New model files are downloaded on the next app restart** — not on-the-fly while
  the worker is already running.

**Config-change lifecycle:**
```
User changes model on ModelPage
        ↓
DB row updated (ai_model_configs.model_name = "new/model")
        ↓
User restarts the app
        ↓
Worker process starts → on_startup() → _get_model()
        ↓
_read_model_config_from_db() → reads new model name
        ↓
from_pretrained("new/model")  ← downloads if not cached, loads into RAM
        ↓
Worker ready with new model
```

### DB config reader (in each queue file)

Each queue file contains a small `_read_model_config_from_db()` helper that uses plain
`sqlite3` — no SQLAlchemy, no ORM, no app-level imports — to stay lightweight and avoid
circular import chains in worker processes.

```python
import sqlite3, os

def _read_model_config_from_db() -> dict | None:
    """Read this model's config directly from the main DB using plain sqlite3."""
    db_path = os.path.join(os.getcwd(), "../db.sqlite3")
    try:
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT model_name, mode FROM ai_model_configs WHERE type = ?",
            ("clip",)   # ← each queue file uses its own type string
        ).fetchone()
        conn.close()
        if row:
            return {"model_name": row[0], "mode": row[1]}
    except Exception as e:
        logger.warning(f"[clip_queue] Could not read config from DB: {e}")
    return None
```

### Pattern (one per queue file)

```python
# queues/clip_queue.py
import threading, json, os, sqlite3
from huey import SqliteHuey
from loguru import logger
from src.db.task_results import save_result

clip_queue = SqliteHuey("clip", filename=os.path.join(os.getcwd(), "../clip.sqlite3"))

_model = None
_lock = threading.Lock()
_DEFAULT_MODEL_NAME = "ViT-B-32"   # fallback when DB has no row yet


def _read_model_config_from_db() -> dict | None:
    db_path = os.path.join(os.getcwd(), "../db.sqlite3")
    try:
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT model_name, mode FROM ai_model_configs WHERE type = ?", ("clip",)
        ).fetchone()
        conn.close()
        return {"model_name": row[0], "mode": row[1]} if row else None
    except Exception as e:
        logger.warning(f"[clip_queue] DB read failed: {e}")
        return None


def _get_model():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                config = _read_model_config_from_db()
                model_name = config["model_name"] if config else _DEFAULT_MODEL_NAME
                logger.info(f"[clip_queue] Loading model: {model_name}")
                from src.ai.clip import ClipTagger
                # ClipTagger.__init__ accepts model_name; downloads from HuggingFace if not cached
                tagger = ClipTagger(model_name=model_name)
                tagger.load_model()                  # ← triggers download if needed
                tagger.load_tags()
                tagger.load_or_compute_categories()
                _model = tagger
                logger.info(f"[clip_queue] Model ready: {model_name}")
    return _model


@clip_queue.on_startup()
def warm():
    _get_model()   # blocks until model is loaded/downloaded; worker accepts tasks only after this


@clip_queue.task()
def call_local_clip_model(task_id: str, file_path: str, task: str = "tags") -> None:
    try:
        model = _get_model()
        with _lock:       # serialize GPU/CPU inference across Huey threads
            if task == "tags":
                result = model.find_tags(file_path)
            elif task == "categorize":
                result = model.categorize(file_path)
            elif task == "encode_image":
                result = model.encode_image(file_path)  # returns list[float]
            else:
                raise ValueError(f"Unknown task: {task}")
        save_result(task_id, json.dumps(result))
    except Exception as e:
        logger.error(f"[clip_queue] {task} failed for {file_path}: {e}")
        save_result(task_id, json.dumps({"error": str(e)}))
```

**Key rules:**
- `_model`, `_lock`, `_DEFAULT_MODEL_NAME` are module-level (per-process singleton).
- `_get_model()` uses double-checked locking — safe for Huey's `--worker-type thread`.
- `_read_model_config_from_db()` reads model name from DB at first load; subsequent
  calls return the already-loaded `_model` without hitting the DB again.
- The inference `with _lock:` ensures only one thread uses the GPU/CPU at a time.
- `save_result` is the ONLY cross-process call. No SQLAlchemy, no main DB access.
- Errors are saved to `task_results.db` so callers get an exception, not a timeout.
- `on_startup()` blocks until the model is in RAM — the worker does not accept tasks
  until the download + load completes. This is the correct behavior.

### Model name → download mapping per queue

| Queue type | `ai_model_configs.type` | Download mechanism | Default fallback |
|---|---|---|---|
| `clip_queue` | `"clip"` | `open_clip.create_model_and_transforms(model_name, pretrained=...)` | `"ViT-B-32"` |
| `vision_queue` | `"vision"` | `AutoModelForCausalLM.from_pretrained(model_name)` — HF auto-download | `"Qwen/Qwen2-VL-2B-Instruct"` |
| `embedding_queue` | `"embedding"` | `SentenceTransformer(model_name)` — HF auto-download | `"nomic-ai/nomic-embed-text-v1.5"` |
| `translation_queue` | `"translator"` | `AutoModelForSeq2SeqLM.from_pretrained(model_name)` — HF auto-download | `"facebook/nllb-200-distilled-600M"` |
| `ocr_queue` | `"ocr"` | `easyocr.Reader(...)` — downloads models to `~/.EasyOCR/` on first use | `"easyocr"` |

CLIP uses `open_clip` (not HuggingFace), so its model name format is `"ViT-B-32"` +
`pretrained="laion2b_s34b_b79k"`. The DB row `model_name` for CLIP stores the
architecture name; the pretrained weights name remains in `CLIP_Settings` or can be
added as a second DB column in the future.

### Queue files to create/update

| File | Action | Model | New tasks |
|---|---|---|---|
| `queues/clip_queue.py` | Update | ClipTagger | `call_local_clip_model(task_id, file_path, task)` |
| `queues/vision_queue.py` | Update | QwenVisionGenerator | `call_local_vision_model(task_id, file_path, prompt_key)` |
| `queues/embedding_queue.py` | Update | SentenceTransformer | `call_local_embedding_model(task_id, text, purpose)` |
| `queues/translation_queue.py` | Update | Translator | `call_local_translation_model(task_id, text, backward)` |
| `queues/ocr_queue.py` | Create | EasyOCRReader | `call_local_ocr_model(task_id, file_path)` |
| `queues/folder_scan_queue.py` | Keep as-is | — | `start_folder_scanner_task` |

`call_local_clip_model` task parameter `encode_image` is new — returns `list[float]`
needed by `compare_photos_deep` and `estimate_photo_quality_deep` tools.

---

## Part 2 — Complete `model_services.py`

Add missing `call_vision_model` and `call_ocr_model`. Extend CLIP to support image encoding.

### Mode check reads from DB too

`model_services.py` must also read `mode` from the DB (not from env-var config) so it
routes to local Huey vs remote HTTP using the same source of truth as the worker.

```python
def _get_mode(model_type: str) -> str:
    """Read mode from main DB. Falls back to settings if DB is unavailable."""
    import sqlite3, os
    db_path = os.path.join(os.getcwd(), "../db.sqlite3")
    try:
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT mode FROM ai_model_configs WHERE type = ?", (model_type,)
        ).fetchone()
        conn.close()
        if row:
            return row[0]
    except Exception:
        pass
    # fallback to env-var settings
    ...
```

This ensures that when the user switches CLIP from "local" to "remote" on the ModelPage,
`model_services.call_clip_model` immediately starts routing to the remote API (no
restart needed for the routing change — only the local worker needs a restart to pick up
a new local model name).

### Full async interface

```python
# src/model_services.py

async def call_clip_model(file_path: str, task: str = "tags") -> list:
    """task: 'tags' → list[tuple[str,float]]
             'categorize' → list[tuple[str,float]]
             'encode_image' → list[float]  (image feature vector)"""

async def call_vision_model(file_path: str, prompt_key: str) -> str:
    """Returns generated text (description or yes/no for is_document)."""

async def call_embedding_model(text: str, purpose: str = "search") -> list[float]:
    """purpose: 'search' | 'save'"""

async def call_translation_model(text: str, backward: bool = False) -> str:
    """Forward: any → user language. Backward: any → English."""

async def call_ocr_model(file_path: str) -> str:
    """Returns extracted text from image."""
```

All functions follow the same pattern:
1. Read mode from settings.
2. If local: generate `task_id = str(uuid4())`, call the Huey task (which enqueues it),
   then `await get_task_result(task_id)`.
3. If remote: `await call_remote_model(url, payload, files, api_key)`.

`get_task_result` in `model_services.py` uses `asyncio.timeout` + `asyncio.sleep`
to poll `task_results.db` without blocking the event loop.

---

## Part 3 — Refactor `tasks/` to Async Pipeline Steps

Tasks in `tasks/` become **async functions** — NOT Huey tasks. They:
- Read from and write to the main DB.
- Call `model_services` for model inference (non-blocking, awaitable).
- No `@queue.task()` decorator. No `registry.*` calls.

### tasks/clip_tasks.py

```python
# Before (Huey task, sync, calls registry directly):
@clip_queue.task()
def auto_tag_clip_task(photo_id, phase, folder_scanner_id=None):
    ...
    confident_tags = registry.clip_tagger.find_tags(photo.file_path)
    ...

# After (async function, calls model_services):
async def process_clip_tags(photo_id: int) -> None:
    db = SessionLocal()
    try:
        photo = get_photo_by_id(db, photo_id)
        if not photo:
            return
        tags: list[tuple[str, float]] = await call_clip_model(photo.file_path, task="tags")
        for tag_name, score in tags:
            add_photo_tag_with_score(db, photo_id, tag_name, score)
        db.commit()
    except Exception as e:
        logger.error(f"[clip_tasks] process_clip_tags failed for {photo_id}: {e}")
        db.rollback()
    finally:
        db.close()

async def process_clip_categories(photo_id: int) -> None:
    # same pattern, task="categorize"
    ...
```

### tasks/vision_tasks.py

```python
async def process_vision_description(photo_id: int) -> None:
    # calls await call_vision_model(file_path, "describe_scene")
    # writes photo.description to DB

async def process_is_document(photo_id: int) -> None:
    # calls await call_vision_model(file_path, "is_document")
    # writes photo.is_doc to DB
```

### tasks/ocr_tasks.py (new file)

```python
async def process_ocr(photo_id: int) -> None:
    # calls await call_ocr_model(file_path)
    # writes photo.ocr_text to DB
```

### tasks/embedding_tasks.py

```python
async def process_embedding(photo_id: int) -> None:
    # builds photo_text from tags/categories/location (DB reads)
    # calls await call_embedding_model(photo_text, purpose="save")
    # stores embedding via store_photo_embedding(...)

async def process_document_embedding(photo_id: int) -> None:
    # reads photo.ocr_text, translates backward if needed
    # calls await call_embedding_model(doc_text_en, purpose="save")
```

### tasks/translation_tasks.py

```python
async def process_translation(photo_id: int) -> None:
    # calls await call_translation_model(photo.description)
    # writes photo.translated_description to DB
```

### tasks/clip_tasks.py — CPU tasks (no model call)

```python
async def process_metadata(photo_id: int) -> None:
    # EXIF, geo, camera — pure CPU, no model_services call

async def process_perceptual_hashes(photo_id: int) -> None:
    # imagehash — pure CPU
```

### tasks/quality_tasks.py — CPU tasks (no model call)

```python
async def process_quality_checks(photo_id: int) -> None:
    # runs all quality checks (brightness, blur, edge, entropy, screenshot) — pure CPU
```

---

## Part 4 — Implement `incoming_pipeline.py`

Replaces the old synchronous job-based pipeline (`tasks/utils.py` dispatcher +
`processing_jobs` string tracking). The new pipeline is a single async coroutine.

```python
# src/incoming_pipeline.py
import asyncio
from loguru import logger
from src.tasks.clip_tasks import (
    process_metadata, process_perceptual_hashes,
    process_clip_tags, process_clip_categories,
)
from src.tasks.vision_tasks import process_vision_description, process_is_document
from src.tasks.ocr_tasks import process_ocr
from src.tasks.embedding_tasks import process_embedding, process_document_embedding
from src.tasks.translation_tasks import process_translation
from src.tasks.quality_tasks import process_quality_checks


async def start_pipeline(photo_id: int, folder_scanner_id: int = None) -> None:
    logger.info(f"[pipeline] Starting for photo {photo_id}")

    # Phase 1 — all parallel (no inter-dependencies)
    await asyncio.gather(
        process_metadata(photo_id),
        process_perceptual_hashes(photo_id),
        process_clip_tags(photo_id),
        process_clip_categories(photo_id),
        process_vision_description(photo_id),
        process_ocr(photo_id),
        process_quality_checks(photo_id),
        return_exceptions=True,
    )

    # Phase 2 — depends on phase 1 results in DB
    await asyncio.gather(
        process_is_document(photo_id),      # needs vision desc
        process_translation(photo_id),      # needs vision desc
        process_embedding(photo_id),        # needs tags + desc
        return_exceptions=True,
    )

    # Phase 3 — depends on phase 2
    await process_document_embedding(photo_id)  # needs ocr_text + is_doc

    if folder_scanner_id:
        _update_scanner_progress(folder_scanner_id)

    logger.info(f"[pipeline] Completed for photo {photo_id}")
```

`return_exceptions=True` means a single failing task (e.g. bad image) does not abort
the whole pipeline.

**Folder scanner progress**: Call `update_folder_scanner_progress` once after each photo
finishes (end of `start_pipeline`), or optionally after phase 1 and phase 2.

**Old `processing_jobs` table**: Replace with the new `pipeline_tasks` table described
in Part 4a below. The string-based task-name tracking is no longer needed because the
async pipeline handles ordering natively.

---

## Part 4a — Pipeline Progress Tracking (Processing Page)

### Goal

The user can open a **Processing Page** in the frontend and see, for every photo
currently being processed (or recently processed), the exact status of each phase and
each task within it: pending / running / done / error.

### 4a.1 New ORM model — `PipelineTask`

```python
# src/models.py
class PipelineTask(Base):
    __tablename__ = "pipeline_tasks"

    id          = Column(Integer, primary_key=True)
    photo_id    = Column(Integer, ForeignKey("photos.id", ondelete="CASCADE"), nullable=False)
    phase       = Column(Integer, nullable=False)   # 1, 2, or 3
    task_name   = Column(String, nullable=False)    # e.g. "process_clip_tags"
    status      = Column(String, nullable=False, default="pending")
                  # "pending" | "running" | "done" | "error"
    error_msg   = Column(String, nullable=True)
    started_at  = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow)

    photo = relationship("Photo", backref="pipeline_tasks")
```

Index on `(photo_id, status)` for fast "show all active" queries.

### 4a.2 Pipeline initialization — all rows created upfront

When `start_pipeline(photo_id)` starts, it inserts one `"pending"` row per task
*before* any task runs. This way the UI immediately shows the full task list for the
photo, even though nothing has happened yet.

```python
PIPELINE_PLAN = [
    (1, "process_metadata"),
    (1, "process_perceptual_hashes"),
    (1, "process_clip_tags"),
    (1, "process_clip_categories"),
    (1, "process_vision_description"),
    (1, "process_ocr"),
    (1, "process_quality_checks"),
    (2, "process_is_document"),
    (2, "process_translation"),
    (2, "process_embedding"),
    (3, "process_document_embedding"),
]

async def start_pipeline(photo_id: int, folder_scanner_id: int = None) -> None:
    _init_pipeline_tasks(photo_id, PIPELINE_PLAN)   # bulk INSERT all as "pending"
    ...
    # phases run as before
```

### 4a.3 `track_task` — async context manager

Each pipeline step wraps its body in `track_task`. The function signature stays clean
and no boilerplate is duplicated.

```python
# src/pipeline_tracker.py
from contextlib import asynccontextmanager
from datetime import datetime
from loguru import logger
from src.db.database import SessionLocal


@asynccontextmanager
async def track_task(photo_id: int, phase: int, task_name: str):
    """
    Marks the task as running on entry, done/error on exit.
    Writes to pipeline_tasks in the main DB.
    Uses its own DB session — independent of any session the task function opens.
    """
    _set_status(photo_id, task_name, "running", started_at=datetime.utcnow())
    try:
        yield
        _set_status(photo_id, task_name, "done", completed_at=datetime.utcnow())
    except Exception as e:
        _set_status(photo_id, task_name, "error",
                    error_msg=str(e), completed_at=datetime.utcnow())
        logger.error(f"[pipeline] {task_name} failed for photo {photo_id}: {e}")
        raise   # re-raise so asyncio.gather captures it as an exception


def _set_status(photo_id, task_name, status, **kwargs):
    db = SessionLocal()
    try:
        row = db.query(PipelineTask).filter_by(
            photo_id=photo_id, task_name=task_name
        ).first()
        if row:
            row.status = status
            for k, v in kwargs.items():
                setattr(row, k, v)
            db.commit()
    finally:
        db.close()
```

Usage in every task function:

```python
# src/tasks/clip_tasks.py
async def process_clip_tags(photo_id: int) -> None:
    async with track_task(photo_id, phase=1, task_name="process_clip_tags"):
        db = SessionLocal()
        try:
            photo = get_photo_by_id(db, photo_id)
            tags = await call_clip_model(photo.file_path, task="tags")
            for tag_name, score in tags:
                add_photo_tag_with_score(db, photo_id, tag_name, score)
            db.commit()
        finally:
            db.close()
```

### 4a.4 API endpoints

```
GET  /api/pipeline/active
     → list of photos currently in-flight
       (have at least one task with status "pending" or "running")
     response: [{ photo_id, file_path, tasks: [{phase, task_name, status, ...}] }]

GET  /api/pipeline/recent?limit=50
     → photos whose pipeline completed or errored in the last 24 h
     response: same shape as above

GET  /api/photos/{photo_id}/pipeline
     → all pipeline tasks for a specific photo
     response: [{phase, task_name, status, started_at, completed_at, error_msg}]

DELETE /api/pipeline/{photo_id}
     → manually clear pipeline records for a photo (admin cleanup)
```

These endpoints are read-only (except DELETE). They never call any model.

### 4a.5 Auto-cleanup

When all tasks for a photo reach `"done"` or `"error"`, `start_pipeline` calls
`_cleanup_pipeline_tasks(photo_id)` which deletes all rows for that photo if
`status != "error"`. Rows with errors are kept for 48 h so the user can see what failed.

A background cleanup job (simple periodic task in `folder_scan_queue` or a FastAPI
`lifespan` background task) deletes error rows older than 48 h.

### 4a.6 Frontend — ProcessingPage

```
┌─────────────────────────────────────────────────────────┐
│  Processing                              [Auto-refresh] │
├─────────────────────────────────────────────────────────┤
│  📷 IMG_0042.jpg                          ████░░░  60%  │
│  ├─ Phase 1                                             │
│  │   ✅ process_metadata              done   0.3 s      │
│  │   ✅ process_clip_tags             done   2.1 s      │
│  │   🔄 process_vision_description   running ...        │
│  │   ⏳ process_ocr                  pending            │
│  │   ⏳ process_quality_checks       pending            │
│  ├─ Phase 2                            (waiting)        │
│  │   ⏳ process_embedding             pending            │
│  │   ⏳ process_translation           pending            │
│  └─ Phase 3                            (waiting)        │
│       ⏳ process_document_embedding   pending            │
├─────────────────────────────────────────────────────────┤
│  📷 IMG_0041.jpg                          ██████░  100% │
│  ✅ All done in 14.2 s                                  │
└─────────────────────────────────────────────────────────┘
```

**Update strategy:**
- **Phase 1 (MVP)**: Poll `GET /api/pipeline/active` every 2 s.
  Simple, no SSE infrastructure needed.
- **Phase 2 (upgrade)**: Use SSE via `GET /api/stream/pipeline`.
  The FastAPI event stream pushes `PipelineTask` updates as JSON on every status change.
  Frontend replaces the polling interval with an `EventSource` connection.

SSE implementation sketch (FastAPI):
```python
from sse_starlette.sse import EventSourceResponse

@app.get("/api/stream/pipeline")
async def pipeline_stream_endpoint():
    async def generator():
        while True:
            db = SessionLocal()
            try:
                tasks = get_active_pipeline_tasks(db)
                data = json.dumps([t.dict() for t in tasks])
            finally:
                db.close()
            yield {"data": data}
            await asyncio.sleep(1)
    return EventSourceResponse(generator())
```

### 4a.7 TDD — `tests/test_pipeline_tracker.py`

| Test | What it verifies |
|---|---|
| `test_init_creates_pending_rows` | `_init_pipeline_tasks(photo_id, plan)` creates one row per task, all `"pending"` |
| `test_track_task_sets_running_then_done` | On enter: status = `"running"`, `started_at` set. On exit: `"done"`, `completed_at` set |
| `test_track_task_sets_error_on_exception` | Exception inside `async with track_task(...)` → status = `"error"`, `error_msg` populated, exception re-raised |
| `test_active_endpoint_returns_in_flight` | At least one task `"running"` → photo appears in `/api/pipeline/active` |
| `test_completed_photo_not_in_active` | All tasks `"done"` → photo absent from `active`, present in `recent` |
| `test_cleanup_removes_done_rows` | After pipeline completes without error, rows deleted |
| `test_cleanup_keeps_error_rows` | Error rows not deleted by immediate cleanup |

---

## Part 5 — Fix `folder_scanners.py`

`start_folder_scanner_task` is still a synchronous Huey task that calls sync
`start_pipeline`. Since the new `start_pipeline` is async, call it with `asyncio.run()`:

```python
@folder_scan_queue.task()
def start_folder_scanner_task(path: str) -> bool:
    ...
    for file_path in list_of_photo_paths:
        ...
        photo = create_photo_record(...)
        asyncio.run(start_pipeline(photo.id, folder_scanner.id))
    ...
```

`asyncio.run()` works here because the Huey thread worker is not inside an event loop.
Each call to `start_pipeline` runs to completion before the next photo is processed.

---

## Part 6 — Startup Script reads mode from DB

The startup script (`start_workers.sh` or `start_workers.py`) must read the `mode`
column from `ai_model_configs` to decide which workers to launch. Workers for models
configured as `mode="remote"` are not started.

```python
# backend/start_workers.py
import sqlite3, subprocess, os, sys

DB_PATH = os.path.join(os.path.dirname(__file__), "../db.sqlite3")

def get_modes() -> dict[str, str]:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT type, mode FROM ai_model_configs").fetchall()
    conn.close()
    return {r[0]: r[1] for r in rows}

def main():
    modes = get_modes()
    procs = []

    # Always start
    procs.append(subprocess.Popen([sys.executable, "-m", "huey.bin.huey_consumer",
        "src.queues.folder_scan_queue.folder_scan_queue", "--worker-type", "thread"]))

    # Per-model: only if local
    if modes.get("clip") == "local":
        procs.append(subprocess.Popen([sys.executable, "-m", "huey.bin.huey_consumer",
            "src.queues.clip_queue.clip_queue", "--worker-type", "thread"]))
    if modes.get("vision") == "local":
        procs.append(subprocess.Popen([sys.executable, "-m", "huey.bin.huey_consumer",
            "src.queues.vision_queue.vision_queue", "--worker-type", "thread"]))
    if modes.get("embedding") == "local":
        procs.append(subprocess.Popen([sys.executable, "-m", "huey.bin.huey_consumer",
            "src.queues.embedding_queue.embedding_queue", "--worker-type", "thread"]))
    if modes.get("translator") == "local":
        procs.append(subprocess.Popen([sys.executable, "-m", "huey.bin.huey_consumer",
            "src.queues.translation_queue.translation_queue", "--worker-type", "thread"]))
    if modes.get("ocr") == "local":
        procs.append(subprocess.Popen([sys.executable, "-m", "huey.bin.huey_consumer",
            "src.queues.ocr_queue.ocr_queue", "--worker-type", "thread"]))

    # Wait for all workers
    for p in procs:
        p.wait()

if __name__ == "__main__":
    main()
```

**Restart behavior when model changes:**
1. User opens ModelPage → changes `vision` model name to `"Qwen/Qwen2-VL-7B-Instruct"`
   → frontend writes to `/api/model-configs/vision` → DB row updated.
2. User restarts the app.
3. `start_workers.py` re-reads modes — `vision` is still `"local"` → starts `vision_queue` worker.
4. `vision_queue.warm()` → `_get_model()` → `_read_model_config_from_db()` returns new name.
5. `AutoModelForCausalLM.from_pretrained("Qwen/Qwen2-VL-7B-Instruct")` downloads model
   to HuggingFace cache if not already there, then loads into RAM.
6. Worker is ready with the new model.

---

## Part 8 — Fix `graphs/tools.py` (Async Tools)

LangGraph's `ToolNode` supports async tools natively. Make model-calling tools `async def`.

### Tools to convert to async

| Tool | Current model call | New call |
|---|---|---|
| `search_photos_semantic` | `get_photos_by_vector(db, query, k)` — encodes query internally | `await call_embedding_model(query, "search")` → then DB vector search by embedding |
| `describe_photo` | `registry.generate_vision_text(file_path, ...)` | `await call_vision_model(file_path, "describe_scene")` |
| `estimate_photo_quality_deep` | `registry.clip_tagger.model.encode_image(img)` | `await call_clip_model(file_path, "encode_image")` |
| `compare_photos_deep` | `registry.clip_tagger.model.encode_image(img)` | `await call_clip_model(file_path, "encode_image")` |

### `search_photos_semantic` fix

`get_photos_by_vector` in `db_service.py` currently calls `registry.embedder_encode_text`
internally. This must change: the function should accept a pre-computed embedding:

```python
# db_service.py — new signature
def get_photos_by_vector(db, embedding: list[float], k: int) -> list[tuple[Photo, float]]:
    ...

# tools.py — updated tool
@tool
async def search_photos_semantic(query: str, k: int = 5) -> str:
    embedding = await call_embedding_model(query, purpose="search")
    db = SessionLocal()
    try:
        results = get_photos_by_vector(db, embedding, k)
        ...
    finally:
        db.close()
```

The same change is needed in the `/api/search/` endpoint in `main.py`.

### Tools that stay synchronous (no model call)

All other tools (`get_categories`, `get_tags`, `move_photos`, `archive_photos`,
`compare_photos_quick`, `add_tag_to_photos`, etc.) remain sync — they only touch the
main DB and filesystem.

---

## Part 9 — Fix `main.py`

### 7.1 Search endpoint

```python
# Before (calls embedding model in API process):
async def search_photos_endpoint(request, db, translator=Depends(get_translator)):
    pairs = get_photos_by_vector(db, request.text_query, request.k)

# After (calls model_services, passes embedding to DB):
async def search_photos_endpoint(request, db):
    embedding = await call_embedding_model(request.text_query, purpose="search")
    pairs = get_photos_by_vector(db, embedding, request.k)
```

Remove `translator: Optional[Translator] = Depends(get_translator)` from this endpoint.

### 7.2 Model config reset endpoint

```python
# Line ~536: registry.reset_model(config_type)
# This is fine — registry.reset_model only clears the cached instance,
# does not load any model. Keep as-is, but note it only affects the
# main process's registry (which should have no models loaded by design).
# The actual worker processes need to be restarted to reload with new config.
```

### 7.3 Edit endpoint — recompute embedding

```python
# Line ~678: final_embedding_task(photo_id, phase="edit")
# Replace with background task that calls the async pipeline step:
import asyncio
asyncio.create_task(process_embedding(photo_id))
# Or use FastAPI BackgroundTasks:
background_tasks.add_task(asyncio.run, process_embedding(photo_id))
```

### 7.4 Remove unused imports

Remove `from src.ai.translator import Translator`, `from src.ai.registry import registry`,
and any `from src.tasks.embedding_tasks import final_embedding_task` in `main.py`.

---

## Part 10 — Fix `db/task_results.py`

Current `task_results.py` missing error handling. Add:
- Error state: `save_error(task_id, error_msg)` — stores `{"error": msg}`
- `get_result` should distinguish "pending" (no row yet) from "error" (row with error key)

```python
def save_result(task_id: str, result: str) -> None: ...    # existing
def save_error(task_id: str, error: str) -> None: ...      # new — wraps in {"error": ...}
def get_result(task_id: str) -> str | None: ...            # existing
def cleanup_old_results(max_age_seconds: float = 3600) -> int: ...  # new
```

`model_services.get_task_result` should detect `{"error": ...}` in the result and raise
`RuntimeError`.

---

## Part 11 — TDD Test Plan

### 11.0 `tests/test_queue_db_config_reader.py`

Each `_read_model_config_from_db()` helper in the queue files must be tested in
isolation — it uses plain `sqlite3`, not the ORM stack.

| Test | What it verifies |
|---|---|
| `test_reads_existing_row` | DB has a row for "clip" → correct `model_name` and `mode` returned |
| `test_returns_none_when_no_row` | DB has no row for "clip" → `None` returned |
| `test_returns_none_on_missing_db` | DB file does not exist → `None` returned (no exception) |
| `test_returns_fallback_model_when_db_unavailable` | `_get_model()` uses `_DEFAULT_MODEL_NAME` when reader returns `None` |

### 11.1 `tests/test_task_result_store.py`

| Test | What it verifies |
|---|---|
| `test_save_and_get_str` | roundtrip for a plain string |
| `test_save_and_get_dict` | roundtrip for a JSON-encoded dict |
| `test_pending_then_saved` | thread sleeps 0.2 s then saves; `get_result` returns immediately after |
| `test_get_result_returns_none_when_absent` | returns `None` before anything is saved |
| `test_save_error_stored` | error JSON saved, readable |
| `test_cleanup_removes_old` | rows with old `created_at` deleted |
| `test_concurrent_writers` | 10 threads each save own task_id, all readable |

### 9.2 `tests/test_model_services.py`

Mock the Huey task calls and `get_result`. Verify:
- `call_clip_model` submits the right Huey task and deserializes the result
- `call_vision_model` in remote mode calls `call_remote_model` with correct payload
- `call_embedding_model` raises `RuntimeError` when result contains `{"error": ...}`
- `get_task_result` raises `asyncio.TimeoutError` when result never arrives

### 9.3 `tests/test_pipeline.py`

Mock all `call_X_model` functions. Verify:
- `start_pipeline` calls all phase-1 tasks concurrently (use `asyncio.gather`)
- Phase-2 tasks run only after phase-1 completes
- `process_document_embedding` is skipped when `photo.is_doc` is False
- A single failing phase-1 task does NOT abort the rest (return_exceptions=True)

### 9.4 `tests/test_tools_async.py`

Mock `call_clip_model`, `call_vision_model`, `call_embedding_model`. Verify:
- `describe_photo` calls `call_vision_model` and returns its text
- `search_photos_semantic` calls `call_embedding_model` with `purpose="search"`,
  then passes the embedding to `get_photos_by_vector`
- `estimate_photo_quality_deep` calls `call_clip_model` with `task="encode_image"`

---

## Implementation Phases

### Phase A — Fix broken files (no logic change, just stop the bleeding)

1. Fix `translation_queue.py` syntax error (`import` without module → remove or complete)
2. Fix `incoming_pipeline.py` syntax error (`async start_pipeline` → `async def start_pipeline`)
3. Delete `graphs/ingestion.py` (old prototype)

### Phase B — Complete the queue layer (TDD for task_results + model_services)

1. Write tests for `db/task_results.py` — `test_task_result_store.py`
2. Add `save_error`, `cleanup_old_results` to `db/task_results.py`
3. Write tests for `_read_model_config_from_db()` — `test_queue_db_config_reader.py`
4. Update `clip_queue.py` — per-queue registry, reads model name from DB, `encode_image` variant
5. Update `vision_queue.py` — per-queue registry, reads model name from DB, `call_local_vision_model`
6. Update `embedding_queue.py` — per-queue registry, reads model name from DB
7. Update `translation_queue.py` — fix syntax, per-queue registry, reads model name from DB
8. Create `ocr_queue.py` — per-queue registry, reads model name from DB, `call_local_ocr_model`
9. Write tests for `model_services.py` — `test_model_services.py`
10. Complete `model_services.py` — add `call_vision_model`, `call_ocr_model`; read mode from DB

### Phase C — Pipeline tracker + async pipeline (TDD first)

1. Add `PipelineTask` ORM model + migration, `PipelineTaskSchema`
2. Write `test_pipeline_tracker.py` (all red)
3. Implement `pipeline_tracker.py` — `track_task`, `_init_pipeline_tasks`, `_cleanup_pipeline_tasks`
4. Add DB service functions: `get_active_pipeline_tasks`, `get_recent_pipeline_tasks`
5. Add API endpoints: `/api/pipeline/active`, `/api/pipeline/recent`, `/api/photos/{id}/pipeline`
6. Write `test_pipeline.py` (all red)
7. Convert `tasks/clip_tasks.py` CPU tasks to `async def` functions
3. Convert `tasks/clip_tasks.py` CLIP tasks to `async def` using `call_clip_model`
4. Convert `tasks/vision_tasks.py` to `async def` using `call_vision_model`
5. Create `tasks/ocr_tasks.py` with `async def process_ocr`
6. Convert `tasks/embedding_tasks.py` to `async def` using `call_embedding_model`
7. Convert `tasks/translation_tasks.py` to `async def` using `call_translation_model`
8. Convert `tasks/quality_tasks.py` to `async def` (CPU only, no model_services)
9. Implement `incoming_pipeline.py` (`start_pipeline` with `asyncio.gather`)
10. Update `tasks/__init__.py` — re-export `start_pipeline` from `incoming_pipeline`
11. Update `folder_scanners.py` — use `asyncio.run(start_pipeline(...))`
12. All tests green

### Phase D — Fix API layer

1. Change `db_service.get_photos_by_vector` signature to accept pre-computed embedding
2. Update `main.py` search endpoint — use `await call_embedding_model` + pass embedding
3. Remove `Translator` dependency from search endpoint
4. Fix recompute-embedding call in edit endpoint
5. Remove unused model imports from `main.py`

### Phase D.5 — ProcessingPage frontend

1. Add `PipelineTask`, `PhotoPipelineStatus` types to `api.ts`
2. Add `getPipelineActive()` to `client.ts`
3. Build `ProcessingPage.tsx` — polling every 2 s, phase grouping, status icons
4. Wire `/processing` route in AppRoutes

### Phase E — Fix tools (TDD first)

1. Write `test_tools_async.py` (all red)
2. Make `describe_photo`, `estimate_photo_quality_deep`, `compare_photos_deep` async
3. Update `search_photos_semantic` to use `call_embedding_model` + updated DB function
4. All tests green
5. Test chat agent end-to-end

### Phase F — Startup script

1. Write `backend/start_workers.py` — reads `mode` from `ai_model_configs` DB table,
   starts only workers whose mode is `"local"`
2. Update `install.py` — call `db/task_results.init_db()` on setup

---

## Files to Create / Modify

| File | Action |
|---|---|
| `src/queues/clip_queue.py` | Update: per-queue registry, add `encode_image` variant |
| `src/queues/vision_queue.py` | Update: per-queue registry, add `call_local_vision_model` |
| `src/queues/embedding_queue.py` | Update: per-queue registry |
| `src/queues/translation_queue.py` | Update: fix syntax, per-queue registry |
| `src/queues/ocr_queue.py` | Create: per-queue registry + `call_local_ocr_model` |
| `src/db/task_results.py` | Update: add `save_error`, `cleanup_old_results` |
| `src/model_services.py` | Update: add `call_vision_model`, `call_ocr_model` |
| `src/tasks/clip_tasks.py` | Rewrite: async functions, call model_services |
| `src/tasks/vision_tasks.py` | Rewrite: async functions, call model_services |
| `src/tasks/ocr_tasks.py` | Create: async `process_ocr` |
| `src/tasks/embedding_tasks.py` | Rewrite: async functions, call model_services |
| `src/tasks/translation_tasks.py` | Rewrite: async function, call model_services |
| `src/tasks/quality_tasks.py` | Rewrite: async functions, CPU only |
| `src/tasks/__init__.py` | Update: re-export async `start_pipeline` |
| `src/incoming_pipeline.py` | Implement: async orchestrator |
| `src/tasks/folder_scanners.py` | Update: `asyncio.run(start_pipeline(...))` |
| `src/db_service.py` | Update: `get_photos_by_vector` takes pre-computed embedding |
| `src/graphs/tools.py` | Update: async tools, call model_services |
| `src/main.py` | Update: search uses model_services, remove model imports |
| `src/graphs/ingestion.py` | Delete (old prototype) |
| `backend/start_workers.sh` | Create: conditional queue startup |
| `src/install.py` | Update: call `init_db()` for task_results.db |
| `tests/test_task_result_store.py` | Create |
| `tests/test_model_services.py` | Create |
| `tests/test_pipeline.py` | Create |
| `tests/test_pipeline_tracker.py` | Create |
| `tests/test_tools_async.py` | Create |
| `src/pipeline_tracker.py` | Create: `track_task` context manager, `_init_pipeline_tasks`, `_cleanup_pipeline_tasks` |
| `src/models.py` | Add `PipelineTask` ORM model |
| `src/schemas.py` | Add `PipelineTaskSchema`, `PhotoPipelineStatus` |
| `src/db_service.py` | Add `get_active_pipeline_tasks`, `get_recent_pipeline_tasks`, `get_photo_pipeline_tasks` |
| `src/main.py` | Add `/api/pipeline/active`, `/api/pipeline/recent`, `/api/photos/{id}/pipeline`, `/api/stream/pipeline` endpoints |
| `frontend/src/pages/ProcessingPage.tsx` | Create: ProcessingPage component |
| `frontend/src/pages/ProcessingPage.css` | Create |
| `frontend/src/api/client.ts` | Add `getPipelineActive`, `getPhotoPipeline` API calls |
| `frontend/src/types/api.ts` | Add `PipelineTask`, `PhotoPipelineStatus` types |
| `frontend/src/App.tsx` or router | Add `/processing` route |
