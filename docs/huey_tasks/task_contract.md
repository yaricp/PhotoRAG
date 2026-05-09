# Task Contract — How to Write a Pipeline Task

Every task that participates in the phased pipeline must follow this contract.

## Required signature

```python
@some_queue.task()
def my_task(photo_id: int, phase: str, folder_scanner_id: int = None):
    ...
```

All three parameters are mandatory. `folder_scanner_id` defaults to `None` for observer-triggered photos.

## Required structure

```python
@some_queue.task()
def my_task(photo_id: int, phase: str, folder_scanner_id: int = None):
    from src.tasks.utils import _finish_task   # lazy import avoids circular deps
    db = SessionLocal()
    try:
        photo = get_photo_by_id(db, photo_id)
        if not photo:
            # Photo was deleted — still finish the task so the phase can advance
            db.rollback()
            _finish_task(photo_id=photo_id, phase=phase, name="my_task",
                         folder_scanner_id=folder_scanner_id)
            return

        # --- do actual work ---
        photo.some_field = compute_something(photo.file_path)
        db.commit()

        _finish_task(photo_id=photo_id, phase=phase, name="my_task",
                     folder_scanner_id=folder_scanner_id)

    except Exception as e:
        logger.error(f"[my_task] Error for photo {photo_id}: {e}")
        db.rollback()
        try:
            delete_job(db, photo_id, phase)
            db.commit()
        except Exception:
            db.rollback()
            raise
    finally:
        db.close()
```

## Rules

1. **Always call `_finish_task`** in the success path — even if the photo is missing or there is nothing to do. Without it, the phase will never complete.
2. **Always call `db.rollback()` before `_finish_task`** if you made no changes, or the session is in a failed state.
3. **Never call `_finish_task` in the except block.** If you got here, the phase is aborted. Call `delete_job` instead.
4. **Import `_finish_task` lazily** (inside the function) to avoid circular import at module load time.
5. **Task names must match exactly** what `phase_logic()` returns in the task CSV string and what is passed to `_finish_task(name=...)`. A mismatch means the task is never removed from the `tasks` column and the phase never advances.
6. **Register the task in `phase_logic()`** in `utils.py` under the correct phase, and add the dispatch case to `_dispatch_tasks()`.

## Adding a new pipeline task

1. Write the task function in the appropriate `*_tasks.py` file, decorated with the correct queue
2. Add `"my_task,"` to the correct phase string in `phase_logic()`
3. Add an `elif task_name == "my_task": my_task(...)` branch in `_dispatch_tasks()`
4. The task name passed to `_finish_task(name=...)` must exactly equal the string used in step 2

## Independent tasks (not part of pipeline phases)

Tasks that do not need to block or trigger phase progression should:
- **Not** call `_finish_task`
- **Not** be listed in `phase_logic()`
- Be enqueued directly by the caller
- Handle their own `db.rollback()` / `db.close()` in try/except/finally

Note: `compute_perceptual_hashes_task` was originally independent but has been integrated into phase 1. It now follows the standard pipeline task contract (calls `_finish_task`, listed in `phase_logic("init")`).
