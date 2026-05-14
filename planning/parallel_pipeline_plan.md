# Parallel Pipeline Plan

## Goal

Make photo processing maximally parallel:
- Phase 0 (CPU-only) tasks for **all photos run simultaneously** in a thread pool
- Phase 1–3 (AI model) tasks for **all photos are submitted concurrently** to Huey workers;
  each Huey worker serialises access to its model (GPU/RAM safety)
- Phases within a **single photo** remain sequential (phase N+1 waits for phase N)
- Concurrency capped by `MAX_CONCURRENT_PIPELINES` setting to prevent OOM on large folders
- Both entry points (folder scanner, watchdog observer) share the same mechanism

---

## Root-cause diagnosis

### Problem 1 — Folder scanner is fully sequential
`start_folder_scanner_task` calls `asyncio.run(start_pipeline(photo_id))` inside a `for`
loop.  `asyncio.run()` blocks until **all 4 phases** for photo N complete before the loop
body runs photo N+1.

```
for file_path in all_files:
    asyncio.run(start_pipeline(photo_id))  # ← blocks here until DONE
```

### Problem 2 — Phase 0 tasks block the event loop
All phase 0 tasks are `async def` but their bodies are pure sync code (PIL image open,
EXIF parsing, imagehash, numpy).  Inside `asyncio.gather`, they execute one at a time
because they never yield control to the event loop.

### Problem 3 — Observer submits the sync wrapper, not the coroutine
`observer.py` imports `start_pipeline` from `src.tasks` (the sync wrapper that calls
`asyncio.run(...)` internally), then passes the *return value* (None) to
`asyncio.run_coroutine_threadsafe`.  The pipeline actually runs synchronously in the
watchdog thread and the `run_coroutine_threadsafe` call silently fails.

---

## Solution overview

```
┌──────────────────────────────────────────────────────────────┐
│  Folder scanner (Huey thread)                                │
│                                                              │
│  Pass 1: register ALL photos → list of photo_ids            │
│  Pass 2: asyncio.run(                                        │
│            run_pipelines_batch(photo_ids, scanner_id)        │
│          )                                                   │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│  Observer (watchdog thread)                                  │
│                                                              │
│  on_created → create photo → run_coroutine_threadsafe(       │
│                 start_pipeline(photo_id), self._loop         │
│               )                                              │
│  (each photo submitted to the shared event loop immediately; │
│   they all run concurrently on that loop)                    │
└──────────────────────────────────────────────────────────────┘

                    ┌─────────────────────────────────┐
                    │  incoming_pipeline.py            │
                    │                                  │
                    │  run_pipelines_batch(ids, sid)   │
                    │    sem = Semaphore(MAX)           │
                    │    gather(*[                     │
                    │      _guarded(start_pipeline(id))│
                    │      for id in ids               │
                    │    ])                            │
                    │                                  │
                    │  start_pipeline(photo_id, sid)   │
                    │    phase 0: gather(              │
                    │      asyncio.to_thread(task, id) │  ← CPU tasks run in OS threads
                    │      for each phase-0 task       │
                    │    )                             │
                    │    phase 1: gather(model tasks)  │  ← submit to Huey, poll async
                    │    phase 2: gather(model tasks)  │
                    │    phase 3: gather(model tasks)  │
                    └─────────────────────────────────┘

                    ┌─────────────────────────────────────────┐
                    │  Huey workers (separate OS processes)    │
                    │                                          │
                    │  clip_queue   (-w 1) — one at a time     │
                    │  vision_queue (-w 1) — one at a time     │
                    │  embedding_q  (-w 1) — one at a time     │
                    │  ocr_queue    (-w 1) — one at a time     │
                    │  translation  (-w 1) — one at a time     │
                    │                                          │
                    │  Multiple photos' tasks queue up;        │
                    │  worker processes them in FIFO order.    │
                    │  This is correct: GPU/RAM safety.        │
                    └─────────────────────────────────────────┘
```

---

## Concurrency model

| Layer | Mechanism | Limiter |
|---|---|---|
| Phase 0 CPU tasks (per photo) | `asyncio.to_thread()` → OS thread pool | Python default threadpool (min(32, cpu+4)) |
| Concurrent photo pipelines | `asyncio.Semaphore(MAX_CONCURRENT_PIPELINES)` | `TaskQueue_Settings.MAX_CONCURRENT_PIPELINES` (default 8) |
| Model tasks (phase 1–3) | Huey queue → worker process | Huey `-w N` flag (default 1 per model type) |

---

## Files changed

### 1. `src/config.py`
Add `MAX_CONCURRENT_PIPELINES: int = 8` to `TaskQueue_Settings`.

### 2. `src/tasks/clip_tasks.py`
- Extract sync bodies of `metadata_task` and `compute_perceptual_hashes_task`
  into `_metadata_sync(photo_id)` and `_perceptual_hashes_sync(photo_id)`.
- Call them via `await asyncio.to_thread(fn, photo_id)` so they run in OS threads
  without blocking the event loop.
- Keep `async with track_task(...)` wrapper on the outside so progress is still tracked.

### 3. `src/tasks/quality_tasks.py`
- Extract sync body of `_quality_task` inner work into `_quality_check_sync(photo_id, check_fn, issue_type)`.
- Call via `await asyncio.to_thread(fn, ...)`.

### 4. `src/incoming_pipeline.py`
- Keep `start_pipeline(photo_id, folder_scanner_id)` unchanged (single-photo pipeline).
- Add `run_pipelines_batch(photo_ids, folder_scanner_id)`:
  - Creates `asyncio.Semaphore(MAX_CONCURRENT_PIPELINES)`
  - Wraps each `start_pipeline` call with the semaphore
  - `asyncio.gather(*all_wrapped_calls, return_exceptions=True)`

### 5. `src/queues/folder_scan_queue.py`
Two-pass rewrite of `start_folder_scanner_task`:
- **Pass 1 (sync)**: walk directory → hash → DB check → create photo records → collect `photo_ids`
- **Pass 2 (async)**: `asyncio.run(run_pipelines_batch(photo_ids, scanner_id))`
- Duplicate photos and progress updates stay in pass 1 as before.

### 6. `src/observer.py`
- Import `start_pipeline` from `src.incoming_pipeline` (the async coroutine function).
- Replace the broken `asyncio.run_coroutine_threadsafe(start_pipeline(photo.id), loop)`
  with `asyncio.run_coroutine_threadsafe(start_pipeline(photo.id), self._loop)` where
  `start_pipeline` is now the async coroutine (not the sync wrapper).
- The observer's event loop (`self._loop`) runs in its daemon thread and multiplexes
  all concurrent photo pipelines on it naturally.

### 7. `src/tasks/__init__.py`
Remove the unused sync wrapper — no caller needs it after this change.
(Observer uses the async function directly; folder scanner uses `run_pipelines_batch`.)

---

## What does NOT change

- `model_services.py` — already correct; local mode submits Huey task + polls async
- Individual Huey queue files (`clip_queue.py`, `vision_queue.py`, etc.) — unchanged
- `run.py` worker startup — unchanged (workers started per-model as before)
- Phase structure (0→1→2→3 per photo) — unchanged
- `pipeline_tracker.py` / `PipelineTask` DB model — unchanged
- Remote model mode — unchanged (goes through `model_services._call_remote`)

---

## Testing checklist

- [ ] Scan a folder with 10 photos — all phase 0 tasks start immediately in parallel
- [ ] Processing page shows multiple photos in phase_0 simultaneously
- [ ] Phase 1 for photo A starts as soon as photo A's phase 0 is done (not waiting for all photos)
- [ ] Watcher: drop 3 photos into watched folder → all 3 process concurrently
- [ ] Single photo via watcher: pipeline still completes correctly
- [ ] `MAX_CONCURRENT_PIPELINES=2` env var: only 2 pipelines run simultaneously
- [ ] Remote model mode: `_call_remote` still called, no regression
