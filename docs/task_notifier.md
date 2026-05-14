# TaskResultNotifier

**File:** `backend/src/task_notifier.py`  
**Singleton:** `get_notifier()` — one instance for the entire process

---

## What it is

`TaskResultNotifier` is the bridge between an async pipeline coroutine and a Huey
worker process. When `model_services.py` submits a task to a Huey queue (e.g.
`vision_queue`), the worker runs the AI model in a separate process and writes the
result to `task_results.db`. The notifier waits for that row to appear and delivers
the result back to the awaiting coroutine.

---

## The problem it solves

### Without the notifier

Each `call_xxx_model()` in `model_services.py` would need its own poll loop:

```python
# naive approach — one loop per task
while True:
    result = db.query(result_table).filter_by(task_id=task_id).first()
    if result:
        return result.data
    await asyncio.sleep(0.5)  # blocks nothing, but...
```

With 50 photos × 4 AI tasks each → **200 concurrent poll loops**, each opening
a SQLite connection every 0.5 s. SQLite's single-writer lock means these loops
queue up and contend with each other. More importantly, if `db.query()` is called
synchronously it blocks the event loop entirely.

### With the notifier

All 200 waiting coroutines share **one background poll loop per event loop**. That
loop wakes every 0.5 s, runs a single batched `SELECT task_id, result FROM results
WHERE task_id IN (...)` for all pending IDs, then resolves the matching Futures.
200 waiters → 1 query per tick, not 200.

---

## How it works

```
pipeline coroutine                  TaskResultNotifier              Huey worker
─────────────────────               ──────────────────              ───────────
call_vision_model(photo_id)
  │
  ├─ huey_task = vision_queue(...)  ──────────────────────────────► runs model
  │                                                                  writes to
  └─ await notifier.wait_for_result(task_id)                        task_results.db
         │                                                               │
         │  creates Future, stores in _pending[loop_id][task_id]        │
         │  ensures poll loop is running                                 │
         │  suspends (awaits Future)                                     │
         │                                                               │
         │          _poll_loop wakes every 0.5 s                        │
         │          _fetch_batch(all pending ids) ──────────────────────┘
         │          future.set_result(raw_json)
         │
         └─ resumes, returns raw_json
```

### Step by step

1. `model_services._wait_result()` calls `get_notifier().wait_for_result(task_id)`.
2. `wait_for_result()` calls `_ensure_running()` which starts a `_poll_loop` task
   on the current event loop if one isn't already running.
3. A `Future` is created on the current loop and stored in
   `_pending[id(loop)][task_id]`.
4. The coroutine `await`s the Future and suspends.
5. The poll loop wakes, calls `_fetch_batch()` via `asyncio.to_thread()` (so the
   SQLite query never blocks the event loop), and gets back a dict of
   `{task_id: raw_result}` for completed tasks.
6. For each result, the matching Future is resolved: `set_result(raw)` on success,
   `set_exception(RuntimeError(...))` if the worker stored an error payload.
7. The suspended coroutine unblocks and returns the raw JSON string.

---

## Multiple event loops

This process runs **three independent event loops** simultaneously:

| Loop | Where | How it starts |
|---|---|---|
| **uvicorn** | Main process, main thread | FastAPI + all request handlers + AI agent |
| **observer** | Main process, daemon thread | `asyncio.new_event_loop()` in `WatcherService` |
| **folder scanner** | Huey worker process | `asyncio.run(run_pipelines_batch(...))` |

`asyncio.Future` objects are bound to the loop that created them. Calling
`future.set_result()` from a different loop is undefined behaviour (race condition,
silent drop, or crash). To prevent this, all per-loop state is isolated:

```python
# keyed by id(loop) — each loop gets its own dict and poll task
_pending:    dict[int, dict[str, asyncio.Future]]
_poll_tasks: dict[int, asyncio.Task]
```

`_ensure_running()` is called from inside `wait_for_result()`, which is already
running on the target loop, so `asyncio.create_task()` always schedules the poll
coroutine on the correct loop. Each loop's poll task reads only that loop's pending
dict and resolves only that loop's Futures.

---

## Configuration

All settings live in `src/config.py` under `TaskQueue_Settings`:

| Setting | Default | Meaning |
|---|---|---|
| `TASK_RESULT_POLL_INTERVAL` | `0.5` s | How often the poll loop wakes |
| `TASK_RESULT_TIMEOUT` | `600.0` s | Max wait before `asyncio.TimeoutError` |
| `TASK_RESULT_LOG_INTERVAL` | `30.0` s | How often a still-waiting task logs a heartbeat |
| `TASK_RESULTS_DATABASE_NAME` | `../task_results.db` | Path to the Huey results SQLite file |

The DB path is resolved to an absolute path at `__init__` time so it remains
correct regardless of working-directory changes.

---

## Callers

The notifier is only called through `model_services._wait_result()`. All five
model-calling functions follow the same pattern:

```python
# model_services.py
async def call_vision_model(photo_id, prompt_key):
    task_id = vision_queue.enqueue(...)  # submits to Huey
    raw = await _wait_result(task_id)    # blocks until worker finishes
    return json.loads(raw)
```

```
call_clip_model          → clip_queue    → notifier
call_vision_model        → vision_queue  → notifier
call_embedding_model     → embedding_queue → notifier
call_translation_model   → translate_queue → notifier
call_ocr_model           → ocr_queue    → notifier
```

Do **not** call `get_notifier().wait_for_result()` directly from task code — always
go through `_wait_result()` in `model_services.py` so timeout and logging are
consistent.

---

## Lifecycle

### Startup
The poll loop starts automatically on the first `wait_for_result()` call within
each event loop. No explicit `start()` call is required.

### Shutdown
`main.py` calls `get_notifier().stop_all()` in the lifespan teardown, which
cancels all poll tasks across all loops cleanly.

### Poll loop crash resilience
If `_poll_once()` raises an exception (e.g. corrupt result row, SQLite busy),
the error is logged and the loop continues — it does **not** die. If the poll task
itself dies for any other reason, `_ensure_running()` detects `task.done()` on the
next `wait_for_result()` call and restarts it.

---

## Error handling

Huey workers store errors by writing a JSON payload with a reserved key:

```json
{ "__error__": "RuntimeError: model returned empty output" }
```

When `_poll_once()` finds this key in a result, it calls
`future.set_exception(RuntimeError(...))` instead of `set_result()`. The waiting
coroutine receives `RuntimeError` and the pipeline logs it as a task failure.

---

## Adding a new model call

1. Add a new Huey queue in `src/queues/` (or reuse an existing one).
2. Write a Huey task in the corresponding `tasks/` file that writes its result to
   the results DB (or raises and lets Huey record the error).
3. In `model_services.py`, add a new `call_xxx_model()` async function:

```python
async def call_xxx_model(photo_id: int) -> dict:
    task_id = xxx_queue.enqueue(photo_id)
    raw = await _wait_result(task_id, label="xxx")
    return json.loads(raw)
```

No changes to `TaskResultNotifier` are needed — it is model-agnostic.
