# Queues — Reference

## Architecture

Each queue is a `SqliteHuey` instance backed by a dedicated SQLite file. Each queue must be started as a **separate worker process**. Workers do not share memory; each loads its own AI model on startup via the `on_startup()` hook.

```
backend/
├── src/queues/
│   ├── clip_queue.py          → clip.sqlite3 (parent dir)
│   ├── vision_queue.py        → vision.sqlite3
│   ├── embedding_queue.py     → embedding.sqlite3
│   ├── translation_queue.py   → translate.sqlite3
│   └── folder_scan_queue.py   → folder_scan.sqlite3
```

SQLite files are created at `os.path.join(os.getcwd(), "../<name>.sqlite3")` — one directory above `backend/`.

---

## clip_queue

**File:** `src/queues/clip_queue.py`  
**SQLite:** `../clip.sqlite3`

**Startup hook** (`warm_clip`): loads `registry.clip_tagger` into memory.

**Tasks registered:**
- `metadata_task` — EXIF extraction, geocoding, camera linking
- `auto_tag_clip_task` — CLIP zero-shot tag prediction
- `categorize_photo_task` — CLIP zero-shot category prediction
- `compute_perceptual_hashes_task` — dHash/aHash/pHash computation and near-duplicate linking

`metadata_task` does not use GPU but is placed on `clip_queue` because it is fast and does not require the vision or embedding model.

`compute_perceptual_hashes_task` is a **phase 1** pipeline task — it is dispatched via `_dispatch_tasks` alongside the other first-phase tasks and calls `_finish_task` on completion. Hash failure (corrupt image) is non-fatal: the task logs a warning and still calls `_finish_task` so phase 1 can advance.

---

## vision_queue

**File:** `src/queues/vision_queue.py`  
**SQLite:** `../vision.sqlite3`

**Startup hook** (`warm_vision`): loads `registry.vision_generator` into memory.

**Tasks registered:**
- `vision_task` — generates a scene description using the vision LLM
- `ocr_task` — extracts text from the image using EasyOCR
- `is_this_document_task` — classifies whether the image is a document

All three tasks require the vision model and run in phase 1 (`vision_task`, `ocr_task`) or phase 2 (`is_this_document_task`).

---

## embedding_queue

**File:** `src/queues/embedding_queue.py`  
**SQLite:** `../embedding.sqlite3`

**Startup hook** (`warm_embedding`): loads both `registry.nomic_embedder` and `registry.translator`.

**Tasks registered:**
- `final_embedding_task` — encodes scene text (description + tags + categories + location) into a 768-dim vector
- `embedding_document_text_task` — encodes OCR text (translated to English) into a vector for document search

Both tasks run in phase 2 (`final_embedding_task`) or phase 3 (`embedding_document_text_task`).

---

## translate_queue

**File:** `src/queues/translation_queue.py`  
**SQLite:** `../translate.sqlite3`

**Startup hook** (`warm_translator`): loads `registry.translator`.

**Tasks registered:**
- `translate_description_task` — translates `photo.description` into `DEFAULT_LANGUAGE`

Skips silently if `DEFAULT_LANGUAGE == "en"` (no translation needed).

---

## folder_scan_queue

**File:** `src/queues/folder_scan_queue.py`  
**SQLite:** `../folder_scan.sqlite3`

**Startup hook** (`warm_folder_scan_queue`): calls `start_existing_folder_scanners()` — resumes any incomplete scans from a previous run (e.g. after restart).

**Tasks registered:**
- `start_folder_scanner_task` — iterates all image files in a selected folder, creates Photo records, dispatches the pipeline and perceptual hash task for each new file, records exact duplicates for files with the same SHA256

No AI model is loaded by this queue. It is CPU-bound (hashing + DB writes).

---

## Starting workers

Each worker is started with `huey_consumer.py` pointing at the queue instance. Typical command:

```bash
python -m huey.bin.huey_consumer src.queues.clip_queue.clip_queue
python -m huey.bin.huey_consumer src.queues.vision_queue.vision_queue
python -m huey.bin.huey_consumer src.queues.embedding_queue.embedding_queue
python -m huey.bin.huey_consumer src.queues.translation_queue.translate_queue
python -m huey.bin.huey_consumer src.queues.folder_scan_queue.folder_scan_queue
```

All five must be running for the full pipeline to complete. If `vision_queue` is not running, `vision_task` tasks will accumulate in `vision.sqlite3` and phase 1 will never finish.
