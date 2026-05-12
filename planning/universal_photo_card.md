# Universal Photo Card — Implementation Plan

## Scope

Replace the two inconsistent photo views (PhotoDetailPage + inline chat/search card) with a
single universal detail page at `/photo/:id`, and add a new edit page at `/photo/:id/edit`.

## Answers to design decisions

| Question | Decision |
|---|---|
| Where does the card render? | Full page at `/photo/:id` (replaces current PhotoDetailPage) |
| How is "trash" stored? | PhotoQualityIssue with `issue_type = "user_trash"` (unmark removes only that type) |
| Manual tag score | `1.0` (user-confirmed = maximum confidence) |
| Map link service | Google Maps (`https://maps.google.com/?q=lat,lon`) |

---

## Architecture overview

```
/photo/:id          → PhotoDetailPage  (view + flags + delete/archive)
/photo/:id/edit     → PhotoEditPage    (fields + tags + categories)
```

### New backend API surface

| Method | Path | Purpose |
|--------|------|---------|
| PUT | `/api/photos/{id}` | Update description / translated_description / ocr_text; triggers background embedding recompute if description changed |
| PUT | `/api/photos/{id}/flags` | Toggle `is_doc` and/or `is_trash` |
| POST | `/api/photos/{id}/tags` | Link a tag by name (create in `tags` table if absent, score=1.0) |
| DELETE | `/api/photos/{id}/tags/{tag_id}` | Unlink a tag from the photo |
| POST | `/api/photos/{id}/categories` | Link a category by name (create in `categories` table if absent, score=1.0) |
| DELETE | `/api/photos/{id}/categories/{cat_id}` | Unlink a category from the photo |

### Schema additions

```python
# Photo response — add computed field
class Photo(BaseModel):
    ...
    is_trash: Optional[bool] = None   # True if issue_type="user_trash" exists

# New request bodies
class PhotoUpdate(BaseModel):
    description: Optional[str] = None
    translated_description: Optional[str] = None
    ocr_text: Optional[str] = None

class PhotoFlagsUpdate(BaseModel):
    is_doc: Optional[bool] = None
    is_trash: Optional[bool] = None

class PhotoTagLink(BaseModel):
    name: str          # tag name from template_tags

class PhotoCategoryLink(BaseModel):
    name: str          # category name from template_categories
```

### New DB service functions (`db_service.py`)

```python
# Trash flag via quality issues
def get_photo_is_trash(db, photo_id) -> bool
def mark_photo_as_trash(db, photo_id) -> None          # adds issue_type="user_trash"
def unmark_photo_as_trash(db, photo_id) -> None        # removes only "user_trash" issues

# Field update
def update_photo_fields(db, photo_id, **fields) -> Optional[Photo]  # description/ocr_text/etc.

# is_doc toggle (direct column update)
def set_photo_is_doc(db, photo_id, value: bool) -> Optional[Photo]

# Manual tag link/unlink
def link_photo_tag(db, photo_id, tag_name) -> PhotoTag   # get_or_create Tag, add PhotoTag score=1.0
def unlink_photo_tag(db, photo_id, tag_id) -> bool       # delete PhotoTag row

# Manual category link/unlink
def link_photo_category(db, photo_id, cat_name) -> PhotoCategory   # get_or_create Category, add PhotoCategory score=1.0
def unlink_photo_category(db, photo_id, cat_id) -> bool            # delete PhotoCategory row
```

### Background embedding recompute on description change

When `PUT /api/photos/{id}` is called and `description` has changed, enqueue directly into
the existing Huey embedding worker — no new threads in the API process:

```python
from src.tasks.embedding_tasks import final_embedding_task
final_embedding_task(photo_id, phase="edit")
```

`phase="edit"` is safe because `_finish_task` checks for a `processing_jobs` row matching
`(photo_id, phase)` — none exists for phase `"edit"`, so `_finish_task` early-returns after
the `tasks_row is None` check. The embedding is computed and stored normally; only the
pipeline job-tracking code is skipped, which is correct for a one-off manual recompute.

No new helper function needed — the existing decorated task is called directly.

---

## Universal PhotoDetailPage layout

```
┌─────────────────────────────────────────────────────────┐
│  [← Back]                              [Edit]           │
├─────────────────────────────────────────────────────────┤
│                      IMAGE                              │
├─────────────────────────────────────────────────────────┤
│  /full/path/to/file.jpg                                 │
│  Date taken:  2024-03-15 14:22                          │
│  Location:    New York, NY  · 40.7128°N 74.0060°W       │
│               [Open in Google Maps ↗]                   │
│  Camera:      Canon EOS R5 (Canon)                      │
│  Description: A sunny day at Central Park...            │
│  Translation: Солнечный день в Центральном парке...      │
├─────────────────────────────────────────────────────────┤
│  ☐ Trash    ☐ Document                                  │
│  ▼ Document text    [collapsed by default]              │
│    extracted OCR text here...                           │
│  ▼ Additional data  [collapsed by default]              │
│    file_created_at · captured_at · created_at           │
│    width × height · ISO · aperture · focal_length       │
│    shutter_speed · offset_time                          │
├─────────────────────────────────────────────────────────┤
│              [Archive]   [Delete]                       │
└─────────────────────────────────────────────────────────┘
```

**Collapsible blocks** — "Document text" and "Additional data" are rows that expand/collapse.
"Document text" row is only visible when `is_doc` is true.

**Checkboxes** — Each fires `PUT /api/photos/{id}/flags` on change. Confirmation modal is NOT
shown for checkbox toggles (they are easily reversible). Confirmation modal IS shown for
Archive and Delete.

---

## PhotoEditPage layout (`/photo/:id/edit`)

```
┌─────────────────────────────────────────────────────────┐
│  [← Back to photo]                                      │
├─────────────────────────────────────────────────────────┤
│                      IMAGE                              │
├─────────────────────────────────────────────────────────┤
│  OCR Text:                                              │
│  ┌──────────────────────────────────────────────────┐   │
│  │  (textarea)                                      │   │
│  └──────────────────────────────────────────────────┘   │
│  Description (EN):                                      │
│  ┌──────────────────────────────────────────────────┐   │
│  │  (textarea)                                      │   │
│  └──────────────────────────────────────────────────┘   │
│  Translation (RU):                                      │
│  ┌──────────────────────────────────────────────────┐   │
│  │  (textarea)                                      │   │
│  └──────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────┤
│  Tags:  [dog] [cat] [×]  [+ Manage Tags]               │
│  Categories: [Nature] [×]  [+ Manage Categories]       │
├─────────────────────────────────────────────────────────┤
│                      [Save]                             │
└─────────────────────────────────────────────────────────┘
```

**Tag/Category modals** — full searchable list of template_tags / template_categories.
Checked = linked to this photo; unchecked = not linked.
Clicking a checked item calls `DELETE /api/photos/{id}/tags/{tag_id}`.
Clicking an unchecked item calls `POST /api/photos/{id}/tags` with the template name.

**Save** — calls `PUT /api/photos/{id}` with changed fields. If description changed, the
server triggers a background embedding recompute. A "Saved ✓" feedback appears on success.

---

## Implementation phases

### Phase 1 — TDD: DB service tests (`test_photo_edit_service.py`)
Write tests first, then implement functions in `db_service.py`.

Tests:
- `test_mark_photo_as_trash` — creates issue_type="user_trash" row
- `test_unmark_photo_as_trash` — removes "user_trash" issues, leaves other issue types intact
- `test_get_photo_is_trash` — returns True/False correctly
- `test_update_photo_fields_description` — updates description column
- `test_update_photo_fields_partial` — only updates provided fields, others unchanged
- `test_set_photo_is_doc` — updates is_doc column
- `test_link_photo_tag_creates_tag_if_missing` — creates Tag + PhotoTag with score=1.0
- `test_link_photo_tag_idempotent` — no duplicate PhotoTag if already linked
- `test_unlink_photo_tag` — removes PhotoTag row, returns True
- `test_unlink_photo_tag_missing` — returns False
- `test_link_photo_category_creates_if_missing`
- `test_link_photo_category_idempotent`
- `test_unlink_photo_category`

### Phase 2 — TDD: API endpoint tests (`test_photo_edit_api.py`)
Write tests first, then implement endpoints in `main.py`.

Tests:
- `test_get_photo_includes_is_trash_false` — GET /api/photos/:id returns is_trash=False by default
- `test_get_photo_includes_is_trash_true` — after marking, is_trash=True
- `test_put_photo_updates_description` — 200 with updated field
- `test_put_photo_nonexistent` — 404
- `test_put_flags_is_doc_true` — sets is_doc
- `test_put_flags_is_trash_true` — adds user_trash issue
- `test_put_flags_is_trash_false` — removes user_trash issue
- `test_post_photo_tag` — links tag, returns 201
- `test_post_photo_tag_nonexistent_photo` — 404
- `test_delete_photo_tag` — unlinks, returns 204
- `test_delete_photo_tag_not_linked` — 404
- `test_post_photo_category` — links category, returns 201
- `test_delete_photo_category` — unlinks, returns 204

### Phase 3 — Backend implementation
- Add 7 DB service functions to `db_service.py`
- Add `is_trash` computed field to `Photo` schema (read from quality_issues in GET endpoint)
- Add 6 new endpoints to `main.py`; `PUT /api/photos/{id}` calls `final_embedding_task(photo_id, phase="edit")` when description changes — enqueues into the existing Huey embedding worker, no extra threads
- Add schemas: `PhotoUpdate`, `PhotoFlagsUpdate`, `PhotoTagLink`, `PhotoCategoryLink`

### Phase 4 — Frontend: API client functions (`client.ts`)
```typescript
updatePhoto(id, data: {description?, translated_description?, ocr_text?}): Promise<Photo>
updatePhotoFlags(id, flags: {is_doc?, is_trash?}): Promise<Photo>
linkPhotoTag(photoId, tagName): Promise<PhotoTag>
unlinkPhotoTag(photoId, tagId): Promise<void>
linkPhotoCategory(photoId, catName): Promise<PhotoCategory>
unlinkPhotoCategory(photoId, catId): Promise<void>
```

### Phase 5 — Frontend: Universal PhotoDetailPage
Replace `PhotoDetailPage.tsx` entirely. New components:
- `CollapsibleRow` — a reusable chevron-toggle row used for "Document text" and "Additional data"
- `PhotoFlagsRow` — the trash/document checkboxes, fires flags API on change
- Existing `ConfirmModal` reused for Archive and Delete actions

Styling: new `PhotoDetailPage.css` (existing file replaced).

### Phase 6 — Frontend: PhotoEditPage + tag/category modals
New files:
- `PhotoEditPage.tsx` — the edit form
- `PhotoEditPage.css`
- `TagPickerModal.tsx` — searchable modal over template_tags, shows which are linked to this photo
- `CategoryPickerModal.tsx` — same for template_categories

### Phase 7 — Frontend: routing + cleanup
- Add `<Route path="/photo/:id/edit" element={<PhotoEditPage />} />` to `AppRoutes.tsx`
- Remove old inline photo rendering from `ChatPage` and `SearchPage` result items (they already link to `/photo/:id`)
- Verify `PhotoCard` in Gallery/Documents still routes to `/photo/:id` correctly

---

## Files changed / created

### Backend
| File | Change |
|------|--------|
| `src/schemas.py` | Add `PhotoUpdate`, `PhotoFlagsUpdate`, `PhotoTagLink`, `PhotoCategoryLink`; add `is_trash` to `Photo` |
| `src/db_service.py` | Add 7 new functions |
| `src/main.py` | Add 6 new endpoints |
| `src/tasks/embedding_tasks.py` | No change — `final_embedding_task` called directly with `phase="edit"` |
| `tests/test_photo_edit_service.py` | New — 13 service tests |
| `tests/test_photo_edit_api.py` | New — 13 API tests |

### Frontend
| File | Change |
|------|--------|
| `src/api/client.ts` | Add 6 new API functions |
| `src/pages/PhotoDetailPage.tsx` | Full rewrite |
| `src/pages/PhotoDetailPage.css` | Full rewrite |
| `src/pages/PhotoEditPage.tsx` | New |
| `src/pages/PhotoEditPage.css` | New |
| `src/components/photos/TagPickerModal.tsx` | New |
| `src/components/photos/CategoryPickerModal.tsx` | New |
| `src/pages/AppRoutes.tsx` | Add `/photo/:id/edit` route |

---

## Open questions / deferred
- **Edit button in PhotoCard grid thumbnails** — currently PhotoCard has Archive/Delete only. Adding an Edit button to the thumbnail card is not in scope here; the Edit page is reachable from the detail page via the Edit button.
- **Vector DB deletion on photo delete** — already handled by existing `delete_photo_endpoint`; no change needed.
- **Sorting of linked tags/categories in the edit page** — show linked tags first, then remaining template entries, alphabetically within each group.
