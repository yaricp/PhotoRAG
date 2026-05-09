# Huey Task System — Overview

## What it is

The photo processing pipeline is built on [Huey](https://huey.readthedocs.io/), a lightweight task queue backed by SQLite files. Each worker process runs independently and picks up tasks from its own SQLite database file.

There are **5 separate queues**, each running in its own process with its own AI model loaded in memory:

| Queue name | SQLite file | AI model warmed up | Task module |
|---|---|---|---|
| `clip_queue` | `../clip.sqlite3` | `clip_tagger` | `clip_tasks.py` |
| `vision_queue` | `../vision.sqlite3` | `vision_generator` | `vision_tasks.py` |
| `embedding_queue` | `../embedding.sqlite3` | `nomic_embedder`, `translator` | `embedding_tasks.py` |
| `translate_queue` | `../translate.sqlite3` | `translator` | `translation_tasks.py` |
| `folder_scan_queue` | `../folder_scan.sqlite3` | _(none — CPU only)_ | `folder_scanners.py` |

Each SQLite file lives one directory above `backend/` (next to `docker-compose.yml`).

---

## Entry points that start the pipeline

A new photo enters the system from two places:

| Entry point | File | Trigger |
|---|---|---|
| **Folder scanner** | `src/tasks/folder_scanners.py` | User selects a folder in the UI |
| **Observer** | `src/observer.py` | File system event (watchdog, new file created) |

Both entry points:
1. Compute SHA256 hash of the file
2. Check if that hash already exists in the DB (`check_photo_hash_exists`)
3. **If duplicate**: call `record_exact_duplicate()` and skip full pipeline
4. **If new**: call `create_photo_record()`, then `start_pipeline()` — perceptual hashing is dispatched as part of phase 1

---

## Pipeline phases

`start_pipeline` is defined in `src/tasks/__init__.py`. It uses a 3-phase model:

```
Phase: init
  ↓  phase_logic("init")
Phase: first  — parallel tasks
  metadata_task, auto_tag_clip_task, categorize_photo_task, vision_task, ocr_task, compute_perceptual_hashes_task
  ↓  all six complete → _start_next_phase
Phase: second — parallel tasks
  final_embedding_task, translate_description_task, is_this_document_task
  ↓  all three complete → _start_next_phase
Phase: third  — sequential
  embedding_document_text_task
  ↓  completes → _start_next_phase → phase="" → DONE
```

**Parallel execution is real**: all tasks in a phase are dispatched to their queues at once. They run independently across separate worker processes. The phase advances only when every task in that phase has called `_finish_task`.

---

## ProcessingJob — the phase counter

The `processing_jobs` table has one row per photo per active phase:

| column | purpose |
|---|---|
| `photo_id` | which photo |
| `phase` | `"first"`, `"second"`, or `"third"` |
| `tasks` | comma-separated list of still-pending task names, e.g. `"metadata_task,vision_task,"` |

When a task finishes it atomically removes its own name from `tasks`:

```sql
UPDATE processing_jobs
SET tasks = TRIM(REPLACE(tasks, 'vision_task,', ''))
WHERE photo_id = :id AND phase = :phase
```

When `tasks` becomes an empty string, the phase is complete and `_start_next_phase` fires.

---

## Perceptual hash task (phase 1)

`compute_perceptual_hashes_task` (in `clip_tasks.py`, runs on `clip_queue`) is part of **phase 1** and is dispatched alongside the other first-phase tasks via `_dispatch_tasks`:

- Computes dHash / aHash / pHash with the `imagehash` library
- Stores results in `photo_hashes` table
- Compares against all existing hashes; records near-duplicates (hamming distance ≤ 10) in `photo_duplicates`
- Hash failure is non-fatal: a corrupt image skips hashing but still calls `_finish_task` so the rest of phase 1 can complete normally
