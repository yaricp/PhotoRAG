# Pipeline Async Fix Plan

## Problem

When processing a large batch of photos (e.g. 50), the async event loop is repeatedly
blocked by two categories of synchronous I/O:

### Bottleneck 1 — Per-task polling loop blocks the event loop

`_poll_result()` in `model_services.py` calls `get_result(task_id)` directly on the
event loop thread. `get_result` opens a new SQLite connection, queries, and closes it
synchronously. With N concurrent photos × M model tasks each, there are N×M polling
coroutines — each one blocking the event loop every `TASK_RESULT_POLL_INTERVAL` seconds.

With 8 concurrent photos × 3 phase-1 tasks = 24 sync SQLite reads per 0.5s interval.
The event loop can't do other work while each one runs.

### Bottleneck 2 — Model task DB writes block the event loop

After a model result is received, task functions (e.g. `auto_tag_clip_task`) write
results back to the main DB using synchronous SQLAlchemy — directly on the event loop
thread. With many photos in the same phase simultaneously, these writes queue up behind
each other and block all other coroutines.

---

## Solution

### Change 1 — Shared result notifier (replaces per-task polling)

Create `src/task_notifier.py` — a singleton `TaskResultNotifier` with:

- A dict `{task_id: asyncio.Future}` for all in-flight model calls
- A single background coroutine (`_poll_loop`) that runs one batched
  `SELECT task_id, result FROM results WHERE task_id IN (...)` via
  `asyncio.to_thread()` per interval, covering **all** pending tasks at once
- `async wait_for_result(task_id, timeout)` — creates a Future, stores it, and
  `await`s it; the poll loop resolves it when the result arrives

Effect: N×M individual sync SQLite reads per interval → 1 async read per interval.
The event loop is never blocked by polling.

### Change 2 — Wrap model task DB writes in `asyncio.to_thread()`

Task functions that write to the main DB after receiving a model result must not do
that work directly on the event loop thread. Extract each task's DB read+write body
into a sync helper function and call it via `await asyncio.to_thread(helper, ...)`.

Tasks that need this treatment (phase 1+, which call models then write):

| Task | File |
|---|---|
| `auto_tag_clip_task` | `src/tasks/clip_tasks.py` |
| `categorize_photo_task` | `src/tasks/clip_tasks.py` |
| `vision_task` | `src/tasks/vision_tasks.py` |
| `is_this_document_task` | `src/tasks/vision_tasks.py` |
| `ocr_task` | `src/tasks/vision_tasks.py` |
| `screenshot_detect_task` | `src/tasks/quality_tasks.py` |
| `translate_description_task` | `src/tasks/translation_tasks.py` |
| `final_embedding_task` | `src/tasks/embedding_tasks.py` |
| `embedding_document_text_task` | `src/tasks/embedding_tasks.py` |

Phase 0 tasks are already fully wrapped in `asyncio.to_thread()` — no change needed.

---

## Architecture: TaskResultNotifier

```
┌─────────────────────────────────────────────────────────┐
│  FastAPI event loop                                      │
│                                                          │
│  _poll_loop() ──── every 0.5s ──► asyncio.to_thread()  │
│      │                              │                    │
│      │   SELECT task_id, result     │  sqlite3 (thread) │
│      │   WHERE task_id IN (...)  ◄──┘                   │
│      │                                                   │
│      └──► resolve futures for completed task_ids        │
│                                                          │
│  auto_tag_clip_task()                                    │
│    call_clip_model()                                     │
│      notifier.wait_for_result(task_id) ──► await future │
│                                            │             │
│                              poll loop resolves it ◄────┘
│    asyncio.to_thread(_save_tags_sync, photo_id, tags)   │
└─────────────────────────────────────────────────────────┘
```

---

## Files to create / modify

### New: `src/task_notifier.py`

```python
class TaskResultNotifier:
    _pending: dict[str, asyncio.Future]
    _task: asyncio.Task | None

    def start(self) -> None          # called from app lifespan
    def stop(self) -> None           # called from app lifespan shutdown
    async def wait_for_result(task_id, timeout) -> str
    async def _poll_loop(self) -> None   # one batched SELECT per interval
    @staticmethod
    def _fetch_batch(task_ids) -> dict[str, str]  # runs in thread

_notifier = TaskResultNotifier()     # module-level singleton
```

Error marker detection (currently in `get_result`) moves into `_poll_loop`: if the
stored result JSON contains `{"__error__": "..."}`, call `future.set_exception()`.

### Modified: `src/model_services.py`

- Remove `_poll_result()` entirely
- Each `call_xxx_model` local-mode branch: replace `await _poll_result(task_id, ...)`
  with `await _notifier.wait_for_result(task_id, timeout=...)`

### Modified: `src/main.py`

In the `lifespan` async context manager:
- Startup: `_notifier.start()`
- Shutdown: `_notifier.stop()`

### Modified: `src/tasks/clip_tasks.py`

`auto_tag_clip_task` and `categorize_photo_task`:

```python
async def auto_tag_clip_task(photo_id: int) -> None:
    async with track_task(photo_id, "phase_1", "auto_tag_clip_task"):
        file_path = await asyncio.to_thread(_get_clip_file_path, photo_id)
        if not file_path:
            return
        tags = await call_clip_model(file_path=file_path, task="tags")
        await asyncio.to_thread(_save_tags_sync, photo_id, tags)

def _get_clip_file_path(photo_id: int) -> str | None: ...   # sync DB read
def _save_tags_sync(photo_id: int, tags: list) -> None: ... # sync DB write
```

Same pattern for `categorize_photo_task` with `_save_categories_sync`.

### Modified: `src/tasks/vision_tasks.py`

`vision_task`, `is_this_document_task`, `ocr_task`:
- Extract `_get_vision_file_path(photo_id)` (sync read)
- Extract `_save_description_sync(photo_id, desc)`, `_save_is_doc_sync(photo_id, val)`,
  `_save_ocr_text_sync(photo_id, text)` (sync writes)
- Each async task: read via `to_thread`, await model call, write via `to_thread`

### Modified: `src/tasks/quality_tasks.py`

`screenshot_detect_task` (phases 3 — not phase 0 so not yet wrapped):
- Same pattern: `_get_screenshot_file_path`, `_save_screenshot_result_sync`

### Modified: `src/tasks/translation_tasks.py`

`translate_description_task`:
- Extract `_get_translation_input_sync(photo_id)` (reads description)
- Extract `_save_translation_sync(photo_id, text)` (writes translated_description)

### Modified: `src/tasks/embedding_tasks.py`

`final_embedding_task` and `embedding_document_text_task`:
- These already read several related fields (tags, categories, location, ocr_text)
- Extract `_read_embedding_input_sync(photo_id) -> dict` returning all needed fields
- The actual `store_photo_embedding` call also goes via `to_thread`

---

## Implementation order

1. `src/task_notifier.py` — new file, self-contained, testable in isolation
2. `src/model_services.py` — swap `_poll_result` for `notifier.wait_for_result`
3. `src/main.py` — start/stop notifier in lifespan
4. Task files — wrap DB reads/writes, one file at a time:
   a. `clip_tasks.py` (auto_tag + categorize)
   b. `vision_tasks.py` (vision + is_document + ocr)
   c. `translation_tasks.py`
   d. `embedding_tasks.py`
   e. `quality_tasks.py` (screenshot_detect only)

---

## What does NOT change

- Phase 0 tasks — already fully in `asyncio.to_thread()`, no change
- Huey queue files — unchanged
- `pipeline_tracker.py` / `track_task` — unchanged
- `run.py` worker startup — unchanged
- Phase structure (0→1→2→3→4 per photo) — unchanged
- `MAX_CONCURRENT_PIPELINES` semaphore — unchanged
- Remote model mode — unchanged (no polling involved)

---

## Expected outcome

| Scenario | Before | After |
|---|---|---|
| 1 photo | Fast | Fast (no change) |
| 50 photos, polling | 24 sync SQLite reads / 0.5s | 1 async read / 0.5s |
| 50 photos, DB writes | Sync writes stall event loop | Writes run in threads |
| Model workers | Unchanged | Unchanged |
| Result latency | Delayed by saturated event loop | Near-instant after model finishes |
