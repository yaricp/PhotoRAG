# Pipeline Phases — Detailed Reference

## Phase flow diagram

```
New photo created (observer or folder_scanner)
        │
        ▼
start_pipeline(photo_id, folder_scanner_id?)
        │
        ├─ phase_logic("init") → phase="first"
        │   tasks: metadata_task, auto_tag_clip_task, categorize_photo_task,
        │           vision_task, ocr_task, compute_perceptual_hashes_task
        │
        ├─ get_or_create_job(photo_id, phase="first", tasks=<csv>)
        │   → writes row to processing_jobs
        │
        └─ _dispatch_tasks(photo_id, "first", tasks, folder_scanner_id?)
                │
                ├── metadata_task                   → clip_queue
                ├── auto_tag_clip_task              → clip_queue
                ├── categorize_photo_task           → clip_queue
                ├── vision_task                     → vision_queue
                ├── ocr_task                        → vision_queue
                └── compute_perceptual_hashes_task  → clip_queue


[ Each task runs in its worker process ]
        │
        └─ _finish_task(photo_id, phase, task_name, folder_scanner_id?)
                │
                ├─ SQL: REPLACE tasks column, remove "task_name,"
                ├─ Read remaining tasks
                └─ if remaining == "":
                        ├─ delete_job(photo_id, phase="first")
                        └─ _start_next_phase(photo_id, "first", folder_scanner_id?)


_start_next_phase(photo_id, "first", folder_scanner_id?)
        │
        ├─ phase_logic("first") → phase="second"
        │   tasks: final_embedding_task, translate_description_task, is_this_document_task
        │
        ├─ if folder_scanner_id: update_folder_scanner_progress()
        │
        ├─ get_or_create_job(photo_id, phase="second", tasks=<csv>)
        │
        └─ _dispatch_tasks(photo_id, "second", tasks, folder_scanner_id?)
                │
                ├── final_embedding_task       → embedding_queue
                ├── translate_description_task → translate_queue
                └── is_this_document_task      → vision_queue


[ Same finish logic → _start_next_phase("second") ]


_start_next_phase(photo_id, "second", folder_scanner_id?)
        │
        ├─ phase_logic("second") → phase="third"
        │   tasks: embedding_document_text_task
        │
        └─ _dispatch_tasks → embedding_document_text_task → embedding_queue


[ embedding_document_text_task finishes → _finish_task ]


_start_next_phase(photo_id, "third", folder_scanner_id?)
        │
        └─ phase_logic("third") → next_phase="" → DONE
                └─ if folder_scanner_id: update_folder_scanner_progress() (final step)
```

---

## Task-to-queue mapping

| Task | Queue | AI dependency |
|---|---|---|
| `metadata_task` | `clip_queue` | none (EXIF + geopy) |
| `auto_tag_clip_task` | `clip_queue` | `registry.clip_tagger` |
| `categorize_photo_task` | `clip_queue` | `registry.clip_tagger` |
| `vision_task` | `vision_queue` | `registry.vision_generator` |
| `ocr_task` | `vision_queue` | `extract_text_from_image` (EasyOCR) |
| `final_embedding_task` | `embedding_queue` | `registry.nomic_embedder` |
| `translate_description_task` | `translate_queue` | `registry.translator` |
| `is_this_document_task` | `vision_queue` | `registry.vision_generator` |
| `embedding_document_text_task` | `embedding_queue` | `registry.nomic_embedder`, `registry.translator` |
| `compute_perceptual_hashes_task` | `clip_queue` | `imagehash` (CPU only) — phase 1 |

---

## What each phase task does

### Phase 1 (first)

**`metadata_task`**
- Reads EXIF data from the image file
- Sets `photo.captured_at`, `photo.image_width/height`, `photo.iso`, `photo.aperture`, `photo.focal_length`, `photo.shutter_speed`, `photo.offset_time`
- Creates/links a `Camera` record if make+model present in EXIF
- Geocodes GPS coordinates via `GeoEnricher` → calls `update_photo_geoposition()` (rounds to 3dp, deduplicates)

**`auto_tag_clip_task`**
- Runs the image through CLIP zero-shot tag classification
- Writes tag+confidence pairs to `photo_tags` via `add_photo_tag_with_score()`

**`categorize_photo_task`**
- Runs the image through CLIP zero-shot category classification
- Writes category+confidence pairs to `photo_categories` via `add_photo_category_with_score()`

**`vision_task`**
- Passes the image to the vision LLM with the `describe_scene` prompt
- Stores the generated description in `photo.description`

**`ocr_task`**
- Runs EasyOCR on the image
- If text found, stores in `photo.ocr_text`

**`compute_perceptual_hashes_task`**
- Computes dHash / aHash / pHash using the `imagehash` library
- Stores results in `photo_hashes` table via `get_or_create_photo_hash()`
- Compares against all existing hashes; records near-duplicates (hamming distance ≤ 10) in `photo_duplicates` via `record_perceptual_duplicate()`
- Hash computation is best-effort: a corrupt/unreadable image logs a warning and skips hashing but still calls `_finish_task` so phase 1 can complete

### Phase 2 (second)

**`final_embedding_task`**
- Builds a text string from description + tags + categories + location
- Encodes it with the Nomic text embedder
- Stores the 768-dimensional vector in `photo_embedding_map` + `photo_embeddings_vss` (sqlite-vec)

**`translate_description_task`**
- Translates `photo.description` into the configured `DEFAULT_LANGUAGE` (skips if language is `"en"`)
- Stores in `photo.translated_description`

**`is_this_document_task`**
- Passes the image to the vision LLM with the `is_document` prompt
- Sets `photo.is_doc = True` if the response contains `"yes"`

### Phase 3 (third)

**`embedding_document_text_task`**
- Only runs if `photo.is_doc == True` and `photo.ocr_text` is not empty
- Translates `ocr_text` to English via `registry.translator`
- Encodes the translated text with the Nomic embedder
- Stores the document text vector (separate from the scene vector)

---

## folder_scanner_id and progress tracking

`folder_scanner_id` is optional (only set when the pipeline was started by a folder scan, not by the observer). When present, `_start_next_phase` calls `update_folder_scanner_progress()` at each phase transition. The frontend polls `FolderScanner.scanned_steps / total_steps` to show a progress bar.

Each file counts as 3 steps (one per phase). A file that is an exact duplicate contributes 1 step (the scan step) but skips all pipeline phases.
