# tasks/utils.py — Function Reference

`src/tasks/utils.py` is the orchestration engine for the pipeline. No task logic lives here — only the machinery for advancing the pipeline between phases.

---

## `phase_logic(phase: str) → tuple[str, str]`

Maps the current phase name to the **next phase name** and the **comma-separated task list** for that next phase.

```python
phase_logic("init")   → ("first",  "metadata_task,auto_tag_clip_task,categorize_photo_task,vision_task,ocr_task,")
phase_logic("first")  → ("second", "final_embedding_task,translate_description_task,is_this_document_task,")
phase_logic("second") → ("third",  "embedding_document_text_task,")
phase_logic("third")  → ("", "")   # pipeline complete
```

The trailing comma in each task string is intentional — the `REPLACE` SQL in `_finish_task` removes `"task_name,"` (with comma), so having a trailing comma on every entry makes the pattern consistent.

**Called by:** `start_pipeline` (in `__init__.py`) and `_start_next_phase`.

---

## `_dispatch_tasks(photo_id, phase, tasks, folder_scanner_id=None)`

Sends each task in the `tasks` CSV string to its appropriate queue.

- Imports task functions lazily (inside function body) to avoid circular imports at module load time
- Iterates `tasks.split(",")`, strips whitespace, skips empty strings
- Calls each task function directly — Huey serialises the call into the SQLite file; the matching worker process picks it up
- Logs each dispatch

**Important:** calling a Huey task function (e.g. `vision_task(photo_id, ...)`) does not execute it immediately — it enqueues the call. Execution happens asynchronously in the worker process.

**Called by:** `start_pipeline` and `_start_next_phase`.

---

## `_finish_task(photo_id, phase, name, folder_scanner_id=None)`

The completion callback that every pipeline task must call at the end of its body (including error paths that still want the pipeline to continue).

**Step 1 — Atomic task removal:**
```sql
UPDATE processing_jobs
SET tasks = TRIM(REPLACE(tasks, 'vision_task,', ''))
WHERE photo_id = :photo_id AND phase = :phase
```
This removes the task name (with its trailing comma) from the `tasks` column. `TRIM` removes any leading/trailing whitespace left by the replacement. The UPDATE is committed immediately so other workers see the updated state.

**Step 2 — Read remaining tasks (separate transaction):**
```sql
SELECT tasks FROM processing_jobs WHERE photo_id = :photo_id AND phase = :phase
```
If the row is gone (e.g. job was deleted by an error handler), logs and returns early.

**Step 3 — Check if phase is done:**
- If `remaining == ""` (all tasks removed): calls `delete_job()` then `_start_next_phase()`
- If tasks remain: returns — another worker will eventually call `_finish_task` and complete the phase

**Concurrency safety:** The SQL UPDATE is atomic. Multiple workers can call `_finish_task` concurrently for the same photo/phase without a race condition — only the last worker to remove its task will see `remaining == ""` and trigger `_start_next_phase`.

**Called by:** every pipeline task at the end of its body.

---

## `_start_next_phase(photo_id, phase, folder_scanner_id=None)`

Advances the pipeline to the next phase after the current one completes.

1. Calls `phase_logic(phase)` to determine `next_phase` and `new_tasks`
2. If `folder_scanner_id` is set: calls `update_folder_scanner_progress()` to increment the progress counter
3. If `next_phase == ""`: logs "FINISHED" and returns — pipeline is done
4. Otherwise:
   - Calls `get_or_create_job(photo_id, phase=next_phase, tasks=new_tasks)` to write the new phase row
   - Commits
   - Calls `_dispatch_tasks()` to enqueue the next batch of tasks

**Called by:** `_finish_task` (when `remaining == ""`).

---

## Error handling pattern

Every pipeline task follows the same try/except/finally pattern:

```python
db = SessionLocal()
try:
    # ... do work ...
    db.commit()
    _finish_task(photo_id, phase, "task_name", folder_scanner_id)
except Exception as e:
    logger.error(...)
    db.rollback()
    try:
        delete_job(db, photo_id, phase)  # kill the whole phase on error
        db.commit()
    except Exception:
        db.rollback()
        raise
finally:
    db.close()
```

On error:
- The task's DB changes are rolled back
- `delete_job()` removes the `ProcessingJob` row for this phase — this effectively aborts the pipeline for this photo at the current phase
- `_finish_task` is **not called** — the phase never advances
- The next phase never starts for this photo

This is a "fail fast" approach: one task failure aborts the current phase. There is no automatic retry at the task level.

---

## Notes on the `tasks` column format

The `processing_jobs.tasks` column is a mutable comma-separated string, for example:

```
"metadata_task,auto_tag_clip_task,categorize_photo_task,vision_task,ocr_task,"
```

As tasks complete:
```
"auto_tag_clip_task,categorize_photo_task,vision_task,ocr_task,"   ← metadata_task done
"auto_tag_clip_task,categorize_photo_task,ocr_task,"               ← vision_task done
"auto_tag_clip_task,"                                              ← categorize_photo_task, ocr_task done
""                                                                 ← auto_tag_clip_task done → phase complete
```

The `TRIM(REPLACE(...))` approach works because each task name appears exactly once and always has a trailing comma. The approach is simple but would break if a task name is a substring of another task name — avoid creating tasks whose names are prefixes of existing task names.
