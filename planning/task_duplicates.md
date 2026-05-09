# Duplicates Feature — Implementation Plan

## Goal

Detect and display duplicate photos in two categories:
- **Exact duplicates**: same SHA256 hash (identical file content)
- **Near-duplicates**: perceptual hash (dHash/aHash/pHash) hamming distance ≤ 10

Potential Garbage page is deferred to a later phase.

## Decisions

| Decision | Choice |
|---|---|
| Original in exact duplicate pair | Earliest `captured_at` timestamp |
| Perceptual similarity threshold | Hamming distance ≤ 10 |
| Delete behavior | Delete file from disk + remove DB record |
| Hash scan trigger | Automatically in both new-photo entry points |

---

## Two Entry Points for New Photos

Both paths already call `check_photo_hash_exists()` before creating a Photo record:

| Path | File | Hook line |
|---|---|---|
| **Observer** (real-time file watcher) | `src/observer.py` | ~line 36 |
| **Folder scan task** (user-triggered batch) | `src/tasks/folder_scanners.py` | ~line 51 |

Currently when a hash match is found, both paths just skip the file (`continue`).
We must extend both to **record the duplicate** and **enqueue the perceptual hash task** for every newly created photo.

---

## Data Model

Two new tables added to `src/models.py`:

```
photo_hashes
  id            PK
  photo_id      FK → photos.id (unique)
  dhash         String(16)
  ahash         String(16)
  phash         String(16)

photo_duplicates
  id                  PK
  original_photo_id   FK → photos.id
  duplicate_photo_id  FK → photos.id
  match_type          String  ('exact' | 'perceptual')
  hash_distance       Integer (null for exact)
```

---

## Pipeline Changes

### Stage 1.1 — Exact duplicate detection (both entry points)

**observer.py and folder_scanners.py** — extend the existing `check_photo_hash_exists()` block:

```
current:  if hash exists → skip (continue)
new:      if hash exists → find original by earliest captured_at
                        → call record_exact_duplicate(db, original_id, duplicate_photo_id)
                        → still skip creating a full pipeline for the duplicate
```

### Stage 1.2 — Perceptual hash task (both entry points)

After `create_photo_record()` succeeds in both paths, enqueue a new Huey task:

```
compute_perceptual_hashes_task(photo_id, phase, folder_scanner_id)
```

This task:
1. Opens the image file
2. Computes dHash, aHash, pHash via `imagehash` library
3. Stores results in `photo_hashes`
4. Queries all existing `photo_hashes` rows
5. For each row with hamming distance ≤ 10: calls `record_perceptual_duplicate(db, original_id, new_id, distance)`
6. Original = the one with the earlier `captured_at`

New task lives in a new file `src/tasks/perceptual_hash_tasks.py`, added to an existing queue (e.g. `clip_queue`).

---

## Backend Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/duplicates/` | Returns `{exact: [...groups], perceptual: [...groups]}` |
| DELETE | `/api/photos/{id}` | Extend existing: delete file from disk + remove DB record |

### Response shape for GET /api/duplicates/

```json
{
  "exact": [
    {
      "original": { "id": 1, "file_path": "...", "thumbnail_url": "..." },
      "duplicates": [
        { "id": 2, "file_path": "...", "thumbnail_url": "..." }
      ]
    }
  ],
  "perceptual": [
    {
      "original": { "id": 3, "file_path": "...", "thumbnail_url": "..." },
      "duplicates": [
        { "id": 4, "file_path": "...", "thumbnail_url": "...", "hash_distance": 7 }
      ]
    }
  ]
}
```

---

## Frontend

- New page `DuplicatesPage.tsx` at route `/duplicates`
- Two vertical sections: **Exact Duplicates** / **Near-duplicates**
- Each group: original photo card on left, duplicate(s) on right
- Checkboxes on duplicate cards for selection
- **Delete selected** button in section header
- Link in navigation sidebar

---

## TDD Order (Red → Green → Refactor)

1. `backend/tests/test_models_duplicates.py`
   - PhotoHash model saves and retrieves hashes
   - PhotoDuplicate model links two photos with match_type and distance

2. `backend/tests/test_db_service_duplicates.py`
   - `record_exact_duplicate(db, original_id, duplicate_id)` creates row
   - `get_or_create_photo_hash(db, photo_id, dhash, ahash, phash)` find-or-create
   - `find_perceptual_duplicates(db, photo_id, threshold=10)` returns matching IDs
   - `get_duplicate_groups(db)` returns grouped structure for the API

3. `backend/tests/test_pipeline_exact_duplicate.py`
   - Both observer and folder_scan paths create `photo_duplicates` row on SHA256 collision
   - Earlier `captured_at` photo is chosen as original

4. `backend/tests/test_pipeline_perceptual.py`
   - `compute_perceptual_hashes_task` stores hashes in `photo_hashes`
   - Task creates `photo_duplicates` for photos with distance ≤ 10
   - Task does NOT create duplicates for photos with distance > 10

5. `backend/tests/test_api_duplicates.py`
   - GET `/api/duplicates/` returns correct JSON shape
   - DELETE `/api/photos/{id}` removes file from disk and DB

---

## Implementation Steps (in order)

1. **Dependencies** — Add `imagehash` to `requirements.txt`
2. **Models** — Add `PhotoHash` and `PhotoDuplicate` to `src/models.py`
3. **DB Service** — Add helper functions to `src/db_service.py`
4. **Pipeline — exact** — Extend both `observer.py` and `folder_scanners.py` to call `record_exact_duplicate` on SHA256 collision
5. **Pipeline — perceptual** — Add `src/tasks/perceptual_hash_tasks.py`; enqueue from both entry points after photo creation
6. **API** — Add `/api/duplicates/` endpoint to `src/main.py`; extend DELETE to remove file from disk
7. **Frontend** — `DuplicatesPage.tsx` + route + nav link
