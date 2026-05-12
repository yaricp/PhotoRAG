# Template Tags & Template Categories — Implementation Plan

## Status: APPROVED, ready to implement

---

## Problem

The current system conflates two different roles into single tables:

- `tags` — used both as a CLIP vocabulary AND as photo detection output
- `categories` — seeded during install AND used as photo detection output

This means users cannot manage the CLIP vocabulary without touching photo detection data.

---

## Target Architecture

```
template_tags         → master CLIP vocabulary for tag detection
tags                  → tags detected on specific photos (CLIP output only)
photo_tags            → junction: photo ↔ tag (with confidence score)

template_categories   → master CLIP vocabulary for category detection
categories            → categories detected on specific photos (CLIP output only)
photo_categories      → junction: photo ↔ category (with confidence score)
```

`template_*` tables = source of truth for `.npy` embeddings.
`tags` / `categories` = output tables, populated only by the CLIP pipeline.

---

## Design Decisions (confirmed with user)

| Question | Answer |
|---|---|
| `template_tags.clip_prompt` | Text fed directly to CLIP (e.g. "a photo of a dog"). User-editable per tag. |
| Recalculation trigger | Auto background task after every add / edit / delete |
| Delete template_tag → PhotoTag rows? | Keep existing PhotoTag rows. CLIP just won't detect it on new photos. |
| CLIP tag scope | Strict — CLIP only writes tags that exist in `template_tags` |
| Pagination on TemplateTagsPage | 50 per page (no search field needed) |
| Extra description field? | No — both tables have only `name` + `clip_prompt` |
| Gallery tag cloud | Continues to use `tags` table (detected tags only) |

---

## New DB Tables

```python
class TemplateTag(Base):
    __tablename__ = "template_tags"
    id         = Column(Integer, primary_key=True)
    name       = Column(String, unique=True, nullable=False)
    clip_prompt = Column(String, nullable=False)   # text fed to CLIP
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class TemplateCategory(Base):
    __tablename__ = "template_categories"
    id         = Column(Integer, primary_key=True)
    name       = Column(String, unique=True, nullable=False)
    clip_prompt = Column(String, nullable=False)   # was "prompt" in default_categories.json
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

Existing tables `Tag`, `Category`, `PhotoTag`, `PhotoCategory` — **unchanged**.

---

## New Config Paths (`CLIP_Settings`)

```python
TAGS_NAMES_PATH:       str = "data/tags_names.json"       # ordered list of tag names (index = npy row)
CATEGORIES_NAMES_PATH: str = "data/categories_names.json" # same for categories
```

These JSON files replace `tags_list.txt` as the inference-time name index.
Inference path never hits the DB — it loads `.npy` + `_names.json` only.
DB is needed only at recompute time.

---

## Auxiliary Files (written at recompute time)

```
data/tags_features.npy        — CLIP embeddings ordered by template_tags.id
data/tags_names.json          — ["dog","car",...] same order  ← NEW replaces tags_list.txt
data/tags_content.hash        — MD5 of [(id,name,clip_prompt)] from template_tags
data/tags_model.hash          — unchanged (MD5 of model config)

data/categories_features.npy  — CLIP embeddings ordered by template_categories.id
data/categories_names.json    — ["food","travel",...] same order  ← NEW
data/categories_hash.txt      — MD5 of [(id,name,clip_prompt)] from template_categories
data/categories_model.hash    — unchanged
```

---

## Implementation Phases

### Phase 1 — DB Models + Config  `backend/src/models.py`, `backend/src/config.py`
- [x] Add `TemplateTag` model
- [x] Add `TemplateCategory` model
- [x] Add `TAGS_NAMES_PATH` to `CLIP_Settings`
- [x] Add `CATEGORIES_NAMES_PATH` to `CLIP_Settings`

---

### Phase 2 — Tests (TDD — write BEFORE implementing)  `backend/tests/test_template_service.py`

```
test_create_template_tag
test_get_all_template_tags_paginated
test_update_template_tag_name_and_prompt
test_delete_template_tag_returns_true
test_delete_nonexistent_template_tag_returns_false
test_get_all_template_tags_ordered_by_id

test_create_template_category
test_get_all_template_categories_paginated
test_update_template_category
test_delete_template_category
test_get_all_template_categories_ordered_by_id
```

---

### Phase 3 — DB Service CRUD  `backend/src/db_service.py`

New functions:

```python
# Template Tags
get_all_template_tags(db, skip, limit) -> (list[TemplateTag], int)
get_template_tag_by_id(db, id)         -> Optional[TemplateTag]
get_all_template_tags_ordered(db)      -> list[TemplateTag]  # ordered by id, for npy
create_template_tag(db, name, clip_prompt) -> TemplateTag
update_template_tag(db, id, name, clip_prompt) -> Optional[TemplateTag]
delete_template_tag(db, id)            -> bool

# Template Categories (same pattern)
get_all_template_categories(db, skip, limit) -> (list[TemplateCategory], int)
get_template_category_by_id(db, id)
get_all_template_categories_ordered(db)
create_template_category(db, name, clip_prompt) -> TemplateCategory
update_template_category(db, id, name, clip_prompt) -> Optional[TemplateCategory]
delete_template_category(db, id) -> bool
```

---

### Phase 4 — Pydantic Schemas  `backend/src/schemas.py`

```python
class TemplateTagCreate(BaseModel):
    name: str
    clip_prompt: str

class TemplateTagUpdate(BaseModel):
    name: str
    clip_prompt: str

class TemplateTagResponse(BaseModel):
    id: int
    name: str
    clip_prompt: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

# same pattern: TemplateCategoryCreate, TemplateCategoryUpdate, TemplateCategoryResponse
```

---

### Phase 5 — API Endpoint Tests (TDD)  `backend/tests/test_template_api.py`

```
test_list_template_tags_empty
test_create_template_tag_returns_201
test_create_duplicate_tag_returns_409
test_update_template_tag
test_delete_template_tag
test_list_template_categories
test_create_template_category
test_update_template_category
test_delete_template_category
```

Each write endpoint: verify recompute task was triggered (mock the trigger function).

---

### Phase 6 — API Endpoints  `backend/src/main.py`

```
GET    /api/template-tags/           → paginated (skip, limit)
POST   /api/template-tags/           → create + trigger_recompute_tags()
PUT    /api/template-tags/{id}       → update + trigger_recompute_tags()
DELETE /api/template-tags/{id}       → delete + trigger_recompute_tags()

GET    /api/template-categories/     → paginated
POST   /api/template-categories/     → create + trigger_recompute_categories()
PUT    /api/template-categories/{id} → update + trigger_recompute_categories()
DELETE /api/template-categories/{id} → delete + trigger_recompute_categories()
```

Each write returns immediately with `{"status": "recomputing"}`.
Client polls `GET /api/system/status/` for `clip_tags` or `clip_categories` status.

---

### Phase 7 — Recompute Background Task  `backend/src/tasks/recompute_tasks.py`  (new file)

```python
def trigger_recompute_tags() -> None:
    # sets ModelState("clip_tags", "recomputing")
    # starts daemon Thread → _do_recompute_tags()

def _do_recompute_tags():
    # db = SessionLocal()
    # tagger.load_model()
    # tagger.compute_embeddings_tags_from_db(db)
    # sets ModelState("clip_tags", "ready")

def trigger_recompute_categories() -> None: ...
def _do_recompute_categories(): ...
```

`ModelState` keys for recompute:
- `"clip_tags"` → `"recomputing"` / `"ready"` / `"error"`
- `"clip_categories"` → same

These are initialized in `init_db()` alongside other model states.

---

### Phase 8 — Refactor `clip.py`  `backend/src/ai/clip.py`

#### New method: `compute_embeddings_tags_from_db(db)`
```
1. rows = get_all_template_tags_ordered(db)   # ordered by id
2. names = [r.name for r in rows]
3. prompts = [r.clip_prompt for r in rows]
4. batch encode prompts → npy array
5. np.save(NPY_PATH, array)
6. json.dump(names, open(TAGS_NAMES_PATH))
7. save content hash (MD5 of [(id,name,clip_prompt)])
```

#### New method: `compute_embeddings_categories_from_db(db)`
```
same pattern using template_categories
saves CATEGORIES_NPY_PATH + CATEGORIES_NAMES_PATH + CATEGORIES_HASH_PATH
```

#### Refactor `load_tags()`
```
OLD: reads tags_list.txt
NEW: reads tags_names.json
```

#### Refactor `find_tags()`
- Unchanged in logic, uses new `load_tags()`
- Returns only names from `tags_names.json` → guaranteed to be in template_tags

#### Refactor `load_or_compute_categories()`
```
OLD: reads get_all_categories(db)  (photo-detection table)
NEW: reads get_all_template_categories_ordered(db)
     saves categories_names.json alongside npy
     self.categories_names = names  (list[str], used in categorize())
```

#### Refactor `categorize()`
```
OLD: returns [(cat_id, cat_name, score)]   ← cat_id from categories table
NEW: returns [(cat_name, score)]            ← name from template_categories
```

---

### Phase 9 — Refactor `install.py`  `backend/src/install.py`

#### `install_categories()` (renamed role)
```
OLD: get_or_create_category(db, name, prompt) → writes to "categories"
     update_model_status(db, "categories", "ready")

NEW: get_or_create_template_category(db, name, clip_prompt=prompt)
     update_model_status(db, "template_categories", "ready")
```

#### `install_clip()` — tags section
```
OLD: download CSV → save tags_list.txt → compute_embeddings_tags(tags: list[str])

NEW: download CSV → for each name:
         get_or_create_template_tag(db, name, clip_prompt=name)
     compute_embeddings_tags_from_db(db)
     save tags_model.hash
```

#### `install_clip()` — categories section
```
OLD: tagger.load_or_compute_categories()  (reads categories table)
NEW: tagger.compute_embeddings_categories_from_db(db)  (reads template_categories)
```

#### `_is_categories_cache_valid()` — update hash check
```
OLD: reads get_all_categories(db)
NEW: reads get_all_template_categories_ordered(db)
     computes hash from [(id, name, clip_prompt)]
```

#### `_is_tags_cache_valid()` — add content hash check
```
Add check: tags_content.hash matches MD5 of template_tags contents
(model hash alone is not enough after user edits template_tags)
```

---

### Phase 10 — Refactor `clip_tasks.py`  `backend/src/tasks/clip_tasks.py`

#### `categorize_photo_task()`
```
OLD: for cat_id, cat_name, score in results:
         add_photo_category_with_score(db, photo_id, cat_id, score)

NEW: for cat_name, score in results:
         cat = get_or_create_category(db, cat_name)
         add_photo_category_with_score(db, photo_id, cat.id, score)
```

---

### Phase 11 — Frontend API Client  `frontend/src/api/client.ts`

```typescript
// Template Tags
getTemplateTags(skip: number, limit: number): Promise<PaginatedResponse<TemplateTag>>
createTemplateTag(name: string, clipPrompt: string): Promise<TemplateTag>
updateTemplateTag(id: number, name: string, clipPrompt: string): Promise<TemplateTag>
deleteTemplateTag(id: number): Promise<void>

// Template Categories
getTemplateCategories(skip: number, limit: number): Promise<PaginatedResponse<TemplateCategory>>
createTemplateCategory(name: string, clipPrompt: string): Promise<TemplateCategory>
updateTemplateCategory(id: number, name: string, clipPrompt: string): Promise<TemplateCategory>
deleteTemplateCategory(id: number): Promise<void>
```

---

### Phase 12 — TemplateTagsPage  `frontend/src/pages/TemplateTagsPage.tsx` + `.css`

**Layout:**
```
┌─────────────────────────────────────────────────────┐
│  Template Tags                    [+ Add tag]        │
│  ─────────────────────────────────────────────────  │
│  ⚠ Recalculating embeddings…  (shown when recomputing)│
│  ─────────────────────────────────────────────────  │
│  Name            CLIP Prompt               Actions  │
│  dog             a photo of a dog          ✏ 🗑     │
│  car             a photo of a car          ✏ 🗑     │
│  ...                                                │
│  ─────────────────────────────────────────────────  │
│  ← Prev    Page 1 of 36    Next →                   │
└─────────────────────────────────────────────────────│
```

**Behaviour:**
- "Add tag" → inline row at top with name + clip_prompt inputs (clip_prompt pre-filled from name as user types)
- Edit (✏) → row switches to edit mode in-place
- Delete (🗑) → ConfirmModal
- After any write: banner "Recalculating embeddings…" appears, polls system status, disappears when `clip_tags` = `"ready"`

---

### Phase 13 — TemplateCategoriesPage  `frontend/src/pages/TemplateCategoriesPage.tsx` + `.css`

Same layout and behaviour as TemplateTagsPage, but for categories.
Fewer rows (~50 default categories), so pagination is less critical but still present.

---

### Phase 14 — SettingsPage nav buttons  `frontend/src/pages/SettingsPage.tsx`

Add a new section "Vocabulary" with two navigation link-buttons:

```
┌─────────────────────────────────────────────────────┐
│  VOCABULARY                                          │
│  [Template Tags]   [Template Categories]             │
└─────────────────────────────────────────────────────┘
```

Styled like settings-section, buttons navigate via `useNavigate()`.

---

### Phase 15 — AppRoutes  `frontend/src/pages/AppRoutes.tsx`

```typescript
<Route path="/template-tags"       element={<TemplateTagsPage />} />
<Route path="/template-categories" element={<TemplateCategoriesPage />} />
```

---

## Execution Order (TDD sequence)

```
1.  [DONE] models.py — add TemplateTag, TemplateCategory
2.  [DONE] config.py — add TAGS_NAMES_PATH, CATEGORIES_NAMES_PATH
3.  tests/test_template_service.py — write tests (all fail)
4.  db_service.py — implement CRUD → tests pass
5.  schemas.py — add TemplateTag/Category schemas
6.  tests/test_template_api.py — write tests (all fail)
7.  main.py — add endpoints
8.  tasks/recompute_tasks.py — implement background recompute
9.  → API tests pass
10. clip.py — refactor (compute_embeddings_*_from_db, load_tags from json)
11. install.py — refactor (template tables, new clip.py API)
12. clip_tasks.py — update categorize_photo_task
13. frontend/api/client.ts — add functions
14. TemplateTagsPage.tsx + css
15. TemplateCategoriesPage.tsx + css
16. SettingsPage.tsx — add nav section
17. AppRoutes.tsx — add routes
18. Run full backend tests + frontend tsc check
19. Commit
```

---

## Files Changed / Created

### Backend — modified
- `src/models.py` — new TemplateTag, TemplateCategory models
- `src/config.py` — TAGS_NAMES_PATH, CATEGORIES_NAMES_PATH
- `src/db_service.py` — 12 new CRUD functions
- `src/schemas.py` — 6 new schema classes
- `src/main.py` — 8 new endpoints
- `src/install.py` — refactor install_categories + install_clip
- `src/ai/clip.py` — new compute_from_db methods, load_tags from json
- `src/tasks/clip_tasks.py` — update categorize_photo_task

### Backend — created
- `src/tasks/recompute_tasks.py` — background recompute for tags + categories

### Backend — tests
- `tests/test_template_service.py`
- `tests/test_template_api.py`

### Frontend — modified
- `src/api/client.ts` — 8 new API functions
- `src/pages/AppRoutes.tsx` — 2 new routes
- `src/pages/SettingsPage.tsx` — Vocabulary nav section

### Frontend — created
- `src/pages/TemplateTagsPage.tsx`
- `src/pages/TemplateTagsPage.css`
- `src/pages/TemplateCategoriesPage.tsx`
- `src/pages/TemplateCategoriesPage.css`
