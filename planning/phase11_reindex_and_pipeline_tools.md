# Phase 11 — Re-index Button + Agent Pipeline Tools

## Goal

1. **"Re-index Search" button on PhotoEditPage** — lets the user push the current
   description + tags + categories back into the vector DB after editing, without
   re-running the full AI pipeline.

2. **Agent tool `reindex_photos(photo_ids)`** — lets the AI agent re-save embeddings
   for a list of photos (uses existing description + metadata).

3. **Agent tool `rerun_pipeline_for_photos(photo_ids)`** — lets the AI agent trigger
   the full processing pipeline (phases 0-4) for a list of photos.

---

## Design decisions

### Button placement & name
- **Page**: PhotoEditPage footer, next to the existing "Save" button.
- **Name**: `Re-index Search` — unambiguous; says what it does (updates the search
  vector index) without implying a full AI re-run.
- **Behaviour**: non-blocking — fires the task in the background, shows a brief
  "Queued ✓" feedback, then resets. The user can watch progress on the Processing page.

### API endpoint (for the button)
```
POST /api/photos/{id}/reindex
```
- Fires `final_embedding_task(photo_id)` as a background asyncio task.
- Returns `{"status": "queued", "photo_id": id}` immediately (202-like).
- Requires the photo to have a description; returns 400 if not.

### Agent tools (call pipeline functions directly — no HTTP round-trip)
Both tools are synchronous LangChain `@tool` functions that spawn a background
daemon thread with its own `asyncio.run()` event loop, then return a status string
immediately.

```python
reindex_photos(photo_ids: List[int]) -> str
    # fires final_embedding_task for each ID
    # returns "Re-indexing started for N photo(s)."

rerun_pipeline_for_photos(photo_ids: List[int]) -> str
    # fires run_pipelines_batch(photo_ids)
    # returns "Full pipeline started for N photo(s)."
```

**Why fire-and-forget?**
- Embedding is fast (~1 s/photo) but full pipeline is slow (several minutes).
- Blocking the agent turn would time-out for large batches.
- Users can monitor progress on the Processing page.

**Validation in tools**
- Verify every `photo_id` exists in the DB before firing.
- Reject unknown IDs with a clear message instead of silently skipping them.

---

## File map

### New / changed backend files

| File | Change |
|------|--------|
| `src/main.py` | Add `POST /api/photos/{id}/reindex` endpoint |
| `src/graphs/tools.py` | Add `reindex_photos` and `rerun_pipeline_for_photos` tools |
| `src/graphs/ai_agent.py` | Register both new tools |
| `tests/test_reindex_api.py` | API tests (TDD — written first) |
| `tests/test_reindex_tools.py` | Tool tests (TDD — written first) |

### New / changed frontend files

| File | Change |
|------|--------|
| `src/api/client.ts` | Add `reindexPhoto(id: number)` |
| `src/pages/PhotoEditPage.tsx` | Add Re-index Search button in `pe__footer` |

---

## TDD sequence

### Step 1 — API tests → endpoint

**`tests/test_reindex_api.py`**

```
POST /api/photos/{id}/reindex
  ✓ returns 200 {"status": "queued", "photo_id": id} when photo has a description
  ✓ returns 404 when photo_id does not exist
  ✓ returns 400 when photo exists but has no description
```

Implementation: `final_embedding_task` is mocked — we only verify the endpoint
wires things up correctly, not that the embedding actually runs.

### Step 2 — Tool tests → tools → register in agent

**`tests/test_reindex_tools.py`**

```
reindex_photos
  ✓ returns "started for N photo(s)" string when all IDs exist
  ✓ returns error message when any photo_id does not exist
  ✓ spawns background thread (mock threading.Thread)

rerun_pipeline_for_photos
  ✓ returns "pipeline started for N photo(s)" when all IDs exist
  ✓ returns error message when any photo_id does not exist
  ✓ spawns background thread
```

### Step 3 — Frontend

- `reindexPhoto(id)` in `client.ts` — `POST /api/photos/{id}/reindex`
- PhotoEditPage footer:
  - New state: `reindexing: boolean`, `reindexed: boolean`
  - Button disabled while `reindexing`
  - Shows "Queued ✓" for 2.5 s on success

### Step 4 — Full test suite + commit

---

## Sequence diagram (button flow)

```
User clicks "Re-index Search"
  → POST /api/photos/42/reindex
    → asyncio.create_task(final_embedding_task(42))
    ← {"status": "queued", "photo_id": 42}
  → Button shows "Queued ✓" for 2.5 s

Background (FastAPI event loop):
  final_embedding_task(42)
    → read description + tags + categories + location from DB
    → normalize_for_embedding(...)
    → call_embedding_model(text)
    → store_photo_embedding(db, 42, vector)
```

## Sequence diagram (agent tool flow)

```
User: "Re-index photos 5, 12, 37"
  Agent calls: reindex_photos(photo_ids=[5, 12, 37])
    → validate IDs exist in DB
    → threading.Thread(target=asyncio.run(_embed_all([5,12,37]))).start()
    ← "Re-indexing started for 3 photo(s). IDs: [5, 12, 37]"
  Agent replies to user with confirmation.
```

---

## Open questions / assumptions

- `rerun_pipeline_for_photos` clears `PhotoTag` and `PhotoCategory` rows for each
  photo BEFORE firing the pipeline, so CLIP detection starts from a clean slate and
  doesn't accumulate stale associations.
- The endpoint does NOT validate that a description exists before queuing; the task
  handles the missing-description case gracefully internally.
- Photo IDs that don't exist in the tool call cause the tool to return an error
  string rather than silently ignoring them.
