# Phase 8 — Expanded AI Agent Tools + Docstring Improvements

## Overview

Two parallel workstreams:
1. **Improve docstrings** on all 12 existing tools — write tools must confirm before acting; all tools need non-technical user query examples.
2. **Add 14 new tools** across 5 thematic groups (garbage, quality, duplicates, annotation, search/filter).

---

## Part 1 — Existing Tool Docstring Improvements

### Docstring rule for WRITE tools (filesystem / DB mutations)

Every tool that changes files on disk or data in the database must follow this pattern in its docstring:

```
⚠️ BEFORE CALLING THIS TOOL:
1. Tell the user exactly what will change: which files, folders, or records,
   and what the new state will be.
2. Ask explicitly: "Should I go ahead?" or "Can I proceed?"
3. Only call the tool after the user confirms (yes / ok / go ahead / да / давай).
If the user says no or is unsure, do not call it.
```

### Tools to update

| Tool | Type | Changes needed |
|------|------|----------------|
| `search_photos_semantic` | read | Add non-technical examples |
| `search_photos_by_category_id` | read | Expand — users say "category" in many ways |
| `search_photos_metadata` | read | Add non-technical examples |
| `get_photo_details` | read | Expand — "number", "position", "the one I selected" |
| `get_categories` | read | Add examples |
| `get_tags` | read | Add examples |
| `get_cameras` | read | Add examples |
| `get_geopositions` | read | Add examples |
| `resize_photo` | **write** | Add confirmation requirement + examples |
| `get_exif_data` | read | Add examples |
| `create_folder` | **write** | Add confirmation requirement + examples |
| `move_photos` | **write** | Add confirmation requirement + examples |
| `archive_photos` | **write** | Add confirmation requirement + examples |
| `get_action_history` | read | Add non-technical examples |
| `undo_last_action` | **write** | Add confirmation requirement + examples |
| `describe_photo` | read | Add examples (triggers slow AI inference) |

### Concrete docstring skeletons (write tools)

#### `create_folder`
```
Create a new folder on disk inside the allowed root directory.

⚠️ BEFORE CALLING THIS TOOL — ASK USER PERMISSION:
Tell the user: "I am going to create a new folder called '[folder_name]'
inside [parent_path or 'your photos folder']."
Then ask: "Should I go ahead?"
Only call this tool after the user confirms.

When to use:
- User wants to organise photos into a new folder / album / directory

User query examples (non-technical):
- "Make me a folder called Vacation"
- "I need a new album for my beach photos"
- "Create a place for family pictures"
- "Add a folder named 2024 inside Events"
- "Сделай папку Отпуск"
- "Мне нужна новая папка для праздничных фотографий"
```

#### `move_photos`
```
Move selected photos to a different folder on disk and update their location in the database.

⚠️ BEFORE CALLING THIS TOOL — ASK USER PERMISSION:
Tell the user: "I am going to move [N] photo(s) (IDs: ...) to the folder '[destination_folder]'.
Their files will be physically moved on disk and the database will be updated."
Then ask: "Should I go ahead?"
Only call this tool after the user confirms.

When to use:
- User wants to reorganise, sort, or move photos to another directory

User query examples:
- "Move photo 5 to the Vacation folder"
- "Put these pictures in the Events album"
- "Sort photo number 12 into Family"
- "Send the selected photos to the archive folder"
- "Перемести фото в папку Природа"
```

#### `archive_photos`
```
Pack selected photos into MyPhotoArchive.zip inside the photos root folder
and mark them as archived in the database.

⚠️ BEFORE CALLING THIS TOOL — ASK USER PERMISSION:
Tell the user: "I am going to add [N] photo(s) to MyPhotoArchive.zip and mark them
as archived. They will still exist on disk but will be flagged as archived in the app."
Then ask: "Should I go ahead?"
Only call this tool after the user confirms.

User query examples:
- "Archive these photos"
- "Pack photo 7 into the archive"
- "Zip up the old family pictures"
- "I want to archive the duplicate shots"
- "Добавь эти фотографии в архив"
```

#### `resize_photo`
```
Resize a photo file to a new width and height (overwrites the file on disk).

⚠️ BEFORE CALLING THIS TOOL — ASK USER PERMISSION:
Tell the user: "I am going to resize photo [photo_id] to [width]×[height] pixels.
The original file will be overwritten."
Then ask: "Should I go ahead?"
Only call this tool after the user confirms.

User query examples:
- "Make photo 3 smaller — 800 by 600"
- "Resize picture number 10 to half size"
- "Scale down photo 20 to 1024 wide"
```

#### `undo_last_action`
```
Undo the most recently recorded action (create_folder, move_photos, archive_photos,
add_tag, add_category, add_geoposition).

⚠️ BEFORE CALLING THIS TOOL — ASK USER PERMISSION:
First call get_action_history to show the user what the last action was.
Tell them: "The last action was [action_type] on [timestamp]. I will reverse it."
Ask: "Should I undo this?" Only proceed after confirmation.

User query examples:
- "Undo that"
- "Go back"
- "Revert what you just did"
- "I changed my mind, cancel the last step"
- "Отмени последнее действие"
- "Верни как было"
```

---

## Part 2 — 14 New Tools

### Group A — Garbage / Quality (Tools 1, 2, 3, 5, 15)

#### New helper functions required

**`src/quality_checks.py`** — add:
```python
def compute_colorfulness(file_path: str) -> float:
    """Mean HSV saturation across all pixels (0–255 scale)."""

def get_visual_metrics(file_path: str) -> dict:
    """Aggregate all raw metric values (no garbage judgment).
    Returns: brightness, blur_variance, edge_density, entropy,
             colorfulness, resolution_mpx, width, height."""
```

**`src/db_service.py`** — add:
```python
def get_garbage_photo_paths(db, issue_type: str = None) -> list[str]:
    """Return file_path for all photos flagged with any (or a specific) issue."""
```

#### Tool 1 — `get_garbage_photos`

```python
@tool
def get_garbage_photos(issue_type: str = "", limit: int = 20) -> str:
```

**Docstring:**
```
Show photos that have been detected as potential garbage (low quality).

Read-only — no changes are made.

If issue_type is empty: return a count summary grouped by issue type,
plus a sample of photos from each type (up to limit total).
If issue_type is given: return photos flagged with that specific issue.

Known issue_type values: blur, brightness, resolution, exif, entropy,
edge_density, screenshot.

When to use:
- User asks to see bad/garbage/low-quality/unwanted photos
- User asks which photos should be deleted

User query examples:
- "Show me the bad photos"
- "Which pictures are blurry?"
- "Find photos that are too dark"
- "Show garbage photos"
- "What photos should I delete?"
- "Покажи плохие фотографии"
- "Какие снимки размытые?"
```

Uses: `get_quality_summary`, `get_garbage_photos_with_issues` (new DB function — extends existing `get_photos_by_issue_type` to handle empty issue_type with DISTINCT join).

---

#### Tool 2 — `get_garbage_total_size`

```python
@tool
def get_garbage_total_size(issue_type: str = "") -> str:
```

**Docstring:**
```
Calculate the total file size occupied by potential garbage photos.

Read-only — no files are deleted or changed.

If issue_type is given: count only photos with that specific quality issue.
If empty: count all photos that have any quality issue.

When to use:
- User asks how much space garbage photos take up
- User wants to know how much space could be freed

User query examples:
- "How much space do the bad photos take?"
- "How many gigabytes of garbage photos do I have?"
- "How much disk space could I save by deleting bad photos?"
- "Сколько места занимают плохие фото?"
```

Uses: `get_garbage_photo_paths` (new) + `os.stat` for each path.

---

#### Tool 3 — `estimate_photo_quality_quick`

```python
@tool
def estimate_photo_quality_quick(photo_id: int) -> str:
```

**Docstring:**
```
Run a fast, lightweight quality check on a single photo using pixel-level analysis.
No AI model is loaded — results are available in under a second.

Returns all quality metrics and a garbage verdict:
- brightness (mean luminance 0-255; below 30 = too dark, above 220 = overexposed)
- blur_variance (Laplacian variance; below 100 = blurry)
- edge_density (fraction of edge pixels; below 0.02 = featureless)
- entropy (texture complexity; below 3.0 = repetitive/flat)
- is_screenshot (True if large flat-color regions detected)
- is_thumbnail (True if total pixels < 10 000)
- exif_missing (True if no camera info or capture date)
- overall_verdict: "likely garbage" / "acceptable" / "good"

Read-only — no changes are made to the photo.

When to use:
- User asks if a specific photo is bad / worth keeping
- User wants quick analysis before deciding to delete

User query examples:
- "Is photo 5 any good?"
- "Check if picture number 12 is blurry"
- "Is photo 8 worth keeping?"
- "Analyse the quality of photo 20"
- "Проверь качество фото номер 3"
```

Uses: all 7 `check_*` functions from `quality_checks.py` + `metadata.get_exif_data`.

---

#### Tool 5 — `estimate_photo_quality_deep`

```python
@tool
def estimate_photo_quality_deep(photo_id: int) -> str:
```

**Docstring:**
```
Run a deep AI-based quality assessment using the CLIP vision model.
⏳ Slow — requires loading and running a neural network. Use sparingly.

Compares the photo against 8 quality-related text probes using cosine similarity:
"a blurry photo", "a dark photo", "an overexposed photo", "a screenshot",
"a thumbnail or icon", "a flat featureless image",
"a good quality photo", "a sharp well-lit photo".

Returns similarity score for each probe (0–1) and an overall verdict.

Read-only — no changes are made to the photo.

When to use:
- User wants a deeper AI opinion on photo quality
- Quick check (estimate_photo_quality_quick) was inconclusive

User query examples:
- "Use AI to check if photo 7 is garbage"
- "Do a deep analysis of picture 15"
- "Run the AI quality check on photo 3"
- "Сделай глубокий анализ качества фото 10"
```

Uses: `registry.clip_tagger.model.encode_image`, fixed text probe list, cosine similarity.

---

#### Tool 15 — `get_photo_visual_metrics`

```python
@tool
def get_photo_visual_metrics(photo_id: int) -> str:
```

**Docstring:**
```
Return raw visual measurements for a photo: brightness, blur, sharpness,
edge density, entropy, colorfulness, and resolution.

Unlike estimate_photo_quality_quick, this tool returns only the raw numbers
without any garbage judgment — useful when the user wants to compare or
understand the technical properties of a photo.

Read-only — no changes are made.

When to use:
- User asks about visual properties like brightness, sharpness, colors
- User wants to compare two photos' visual characteristics

User query examples:
- "How bright is photo 5?"
- "Is photo 10 more colorful than average?"
- "What are the visual stats for picture 3?"
- "Show me the sharpness and brightness of photo 7"
- "Какая яркость у фото номер 4?"
```

Uses: `get_visual_metrics` (new function in `quality_checks.py`).

---

### Group B — Duplicate Comparison (Tools 6, 7)

#### Tool 6 — `compare_photos_quick`

```python
@tool
def compare_photos_quick(photo_id_a: int, photo_id_b: int) -> str:
```

**Docstring:**
```
Compare two photos using perceptual hashing (dHash, aHash, pHash).
Fast — no AI model required, runs in milliseconds.

Returns Hamming distance for each hash type (0 = identical, higher = more different)
and a duplicate verdict (distance ≤ 10 on dHash = likely duplicate).

If a photo's hash is not yet stored in the database, it is computed on the fly
and saved automatically for future comparisons.

Read-only comparison — no photos are moved or deleted.

When to use:
- User wants to know if two photos are duplicates
- User has two similar-looking photos and wants a quick check

User query examples:
- "Are photos 5 and 8 the same?"
- "Is picture 12 a duplicate of picture 7?"
- "Compare photo number 3 and photo number 9"
- "These two look the same — check them"
- "Это одно и то же фото?"
- "Сравни фото 4 и фото 11"
```

Uses: `PhotoHash` table (read), `_hamming_distance` from `db_service.py`; if hash missing → `imagehash` library + `get_or_create_photo_hash`.

---

#### Tool 7 — `compare_photos_deep`

```python
@tool
def compare_photos_deep(photo_id_a: int, photo_id_b: int) -> str:
```

**Docstring:**
```
Compare two photos using the CLIP vision model (cosine similarity of image embeddings).
⏳ Slow — requires encoding both images with a neural network.

Returns a similarity score between 0 and 1 (1 = identical, >0.9 = very similar)
and a duplicate verdict.

Use when compare_photos_quick is inconclusive or when visual similarity
matters more than pixel-level matching.

Read-only — no photos are moved or deleted.

When to use:
- Quick hash comparison was inconclusive
- Photos look similar but are different crops or resizes

User query examples:
- "Do a deep check — are photos 5 and 8 really duplicates?"
- "Use AI to compare picture 3 and picture 10"
- "These two look almost the same — AI check please"
- "Сделай глубокое сравнение фото 6 и фото 14"
```

Uses: `registry.clip_tagger.model.encode_image` on both photos, numpy cosine similarity.

---

### Group C — Annotation (Tools 8, 9, 10, 11)

All write tools — all require user confirmation. All save `HistoryAction` for undo.

**Undo support additions in `db_service.perform_undo`:**
- `add_tag` → delete rows from `photo_tags` where `photo_id IN newly_tagged_ids AND tag_id = tag_id`
- `add_category` → delete rows from `photo_categories`
- `add_geoposition` → restore `photo.geoposition_id` from `original_geoposition_ids` dict

#### Tool 8 — `add_tag_to_photos`

```python
@tool
def add_tag_to_photos(photo_ids: List[int], tag_name: str) -> str:
```

**Docstring:**
```
Add a tag to one or more photos in the database.
If the tag does not exist yet, it is created automatically.
Confidence score is set to 1.0 (manually assigned = certain).

⚠️ BEFORE CALLING THIS TOOL — ASK USER PERMISSION:
Tell the user: "I am going to add the tag '[tag_name]' to [N] photo(s) (IDs: ...)."
Ask: "Should I go ahead?"
Only call after confirmation.

Saves a history action — can be undone with undo_last_action.

User query examples:
- "Tag photos 3, 5 and 7 as sunset"
- "Add the label 'family' to these pictures"
- "Mark photo 10 with the tag 'vacation'"
- "Put a 'nature' label on photo 4"
- "Добавь тег 'природа' к фото 3 и 7"
- "Пометь эти снимки как 'важное'"
```

Uses: `get_or_create_tag`, `add_photo_tag_with_score(score=1.0)`, `create_history_action`.

---

#### Tool 9 — `add_category_to_photos`

```python
@tool
def add_category_to_photos(photo_ids: List[int], category_name: str) -> str:
```

**Docstring:**
```
Assign a category to one or more photos in the database.
If the category does not exist yet, it is created automatically.
Confidence score is set to 1.0 (manually assigned = certain).

⚠️ BEFORE CALLING THIS TOOL — ASK USER PERMISSION:
Tell the user: "I am going to assign the category '[category_name]' to
[N] photo(s) (IDs: ...)."
Ask: "Should I go ahead?"
Only call after confirmation.

Saves a history action — can be undone with undo_last_action.

User query examples:
- "Put photo 5 in the Travel category"
- "Categorize pictures 3 and 8 as Food"
- "Assign the Nature category to photo 11"
- "These photos are from the wedding — mark them as Events"
- "Отнеси фото 2, 4, 6 к категории 'Семья'"
```

Uses: `get_or_create_category`, `add_photo_category_with_score(score=1.0)`, `create_history_action`.

---

#### Tool 10 — `add_geoposition_to_photos`

```python
@tool
def add_geoposition_to_photos(
    photo_ids: List[int],
    latitude: float = None,
    longitude: float = None,
    address: str = None,
) -> str:
```

**Docstring:**
```
Set the geographical location for one or more photos.

Accepts either:
- latitude + longitude → automatically reverse-geocodes to get the address
- address (text) → forward-geocodes to get latitude and longitude

⚠️ BEFORE CALLING THIS TOOL — ASK USER PERMISSION:
Tell the user: "I am going to set the location of [N] photo(s) to
[address or lat/lon coordinates]."
Ask: "Should I go ahead?"
Only call after confirmation.

Saves a history action — can be undone with undo_last_action.
Requires an internet connection for geocoding.

User query examples:
- "These photos are from Paris — set the location"
- "Mark photos 3 and 7 as taken in Moscow"
- "Set the location of photo 5 to 48.8566, 2.3522"
- "These are from the Eiffel Tower area"
- "Укажи для этих фото место съёмки: Санкт-Петербург"
- "Поставь геолокацию для фото 8: Москва, Красная площадь"
```

Uses: `GeoEnricher.reverse_geocode` (if lat+lon given) or `GeoEnricher.geolocator.geocode` (if address given), then `update_photo_geoposition`, `create_history_action`.

---

#### Tool 11 — `geocode_photo_from_exif`

```python
@tool
def geocode_photo_from_exif(photo_id: int) -> str:
```

**Docstring:**
```
Read GPS coordinates from a photo's EXIF data and automatically determine
the address using reverse geocoding. Saves the result to the database.

⚠️ BEFORE CALLING THIS TOOL — ASK USER PERMISSION:
Tell the user: "I am going to read the GPS data from photo [photo_id]'s
EXIF information and save the detected location to the database."
Ask: "Should I go ahead?"

This modifies the database (adds or updates geoposition for the photo).
Requires an internet connection.
If the photo has no GPS data in EXIF, returns an error message.

User query examples:
- "Find out where photo 5 was taken"
- "Get the location from the EXIF of picture 12"
- "Read the GPS from photo 7 and save it"
- "Where was photo number 3 shot? Check the EXIF"
- "Определи место съёмки фото 9 по EXIF"
```

Uses: `metadata.get_exif_data`, `GeoEnricher.geocode_photo`, `update_photo_geoposition`.

---

### Group D — Search & Filter (Tools 12, 13, 14)

#### New functions required

**`src/db_service.py`** — add:
```python
def get_photos_by_tag_id(db: Session, tag_id: int) -> List[Photo]:
    """Mirrors get_photos_by_category_id — join photo_tags."""

def search_photos_by_exif_params(
    db: Session,
    width_min: int = None, width_max: int = None,
    height_min: int = None, height_max: int = None,
    focal_length_min: float = None, focal_length_max: float = None,
    aperture_min: float = None, aperture_max: float = None,
    iso_min: int = None, iso_max: int = None,
    camera_make: str = None,
    camera_model: str = None,
    limit: int = 50,
) -> List[Photo]:
    """Filter on Photo columns (image_width, image_height, focal_length,
    aperture, iso) and join Camera for make/model ILIKE matching."""
```

---

#### Tool 12 — `get_photos_by_tag_id`

```python
@tool
def get_photos_by_tag_id(tag_id: int) -> str:
```

**Docstring:**
```
Return all photos that have a specific tag (identified by its numeric ID).

Read-only — no changes are made.

Use get_tags first if you need to find a tag's ID from its name.

When to use:
- User asks to see all photos with a specific tag

User query examples:
- "Show all photos tagged as sunset"           ← first call get_tags, then this
- "Find photos with tag number 3"
- "List all pictures labelled 'family'"
- "Which photos have the 'vacation' tag?"
- "Покажи все фото с тегом 'природа'"
```

Uses: `get_photos_by_tag_id` (new DB function).

---

#### Tool 13 — `search_photos_by_exif`

```python
@tool
def search_photos_by_exif(
    width_min: int = None, width_max: int = None,
    height_min: int = None, height_max: int = None,
    focal_length_min: float = None, focal_length_max: float = None,
    aperture_min: float = None, aperture_max: float = None,
    iso_min: int = None, iso_max: int = None,
    camera_make: str = None,
    camera_model: str = None,
    limit: int = 50,
) -> str:
```

**Docstring:**
```
Search for photos by technical camera parameters stored in EXIF data.

All parameters are optional — combine any subset.
Range parameters (min/max) are inclusive.
camera_make and camera_model are case-insensitive partial matches.

Read-only — no changes are made.

When to use:
- User wants to find photos by resolution, focal length, aperture, ISO, or camera

User query examples:
- "Find all photos taken with a wide angle lens"    (focal_length_max=35)
- "Show photos taken at high ISO"                   (iso_min=3200)
- "Pictures taken with an iPhone"                   (camera_make="apple")
- "Find large photos — wider than 4000 pixels"      (width_min=4000)
- "Photos shot wide open at f/1.8"                  (aperture_max=2.0)
- "Show me shots from my Canon camera"              (camera_make="canon")
- "Найди фотографии с широкоугольным объективом"
- "Покажи снимки с высоким ISO"
```

Uses: `search_photos_by_exif_params` (new DB function).

---

#### Tool 14 — `filter_photos`

```python
@tool
def filter_photos(
    category_ids: List[int] = None,
    tag_ids: List[int] = None,
    camera_id: int = None,
    geoposition_id: int = None,
    is_doc: bool = None,
    year: int = None,
    month: int = None,
    day: int = None,
    limit: int = 50,
    skip: int = 0,
) -> str:
```

**Docstring:**
```
Filter photos using the same criteria available in the Gallery page of the app.
This gives the AI agent full gallery-equivalent filtering power.

All parameters are optional — combine any subset.
Multiple category_ids or tag_ids require ALL of them to be present (AND logic).

Read-only — no changes are made.

When to use:
- User wants to browse or filter photos the same way as in the gallery
- User specifies date, category, tag, camera, or location filters together
- Prefer this over search_photos_metadata when date filters are needed

User query examples:
- "Show me photos from July 2023"                    (year=2023, month=7)
- "Find family photos taken in Paris"               (category_ids=[...], geoposition_id=...)
- "Photos from my Nikon from last summer"           (camera_id=..., year=..., month=...)
- "Document photos from 2022"                       (is_doc=True, year=2022)
- "Show the first 20 nature photos"                 (category_ids=[...], limit=20)
- "Покажи фото за август 2021 года"
- "Найди пейзажи сделанные в Москве"
```

Uses: `get_all_photos` directly (already exists — zero new code in db_service).

---

## Part 3 — Test Plan

5 new test files, ~57 tests total. All follow the established pattern:
- Module-level `sys.modules` mocks (without `'src.graphs'` — only `'src.graphs.ai_agent'`)
- SQLite in-memory DB with `db_factory` fixture (sessionmaker)
- `side_effect=db_factory` when patching `SessionLocal`
- CLIP/AI calls mocked with `patch("src.graphs.tools.registry")`

| File | Tools covered | ~Tests |
|------|--------------|--------|
| `tests/test_tool_garbage.py` | get_garbage_photos, get_garbage_total_size | 10 |
| `tests/test_tool_quality.py` | estimate_photo_quality_quick, estimate_photo_quality_deep, get_photo_visual_metrics | 13 |
| `tests/test_tool_duplicate.py` | compare_photos_quick, compare_photos_deep | 10 |
| `tests/test_tool_annotation.py` | add_tag_to_photos, add_category_to_photos, add_geoposition_to_photos, geocode_photo_from_exif + undo for all 3 | 16 |
| `tests/test_tool_search.py` | get_photos_by_tag_id, search_photos_by_exif, filter_photos | 10 |

---

## Part 4 — Implementation Order

1. **Docstring updates** — `src/graphs/tools.py` (all 12 existing tools)
2. **New utility functions** — `src/quality_checks.py` (colorfulness, get_visual_metrics)
3. **New DB functions** — `src/db_service.py` (4 new functions + extend perform_undo for 3 new action types)
4. **Group A tools** — garbage + quality (Tools 1, 2, 3, 5, 15) + tests
5. **Group B tools** — duplicate comparison (Tools 6, 7) + tests
6. **Group C tools** — annotation (Tools 8, 9, 10, 11) + tests
7. **Group D tools** — search/filter (Tools 12, 13, 14) + tests
8. **Register all 14 tools** in `src/graphs/ai_agent.py`

---

## Part 5 — Summary of All File Changes

| File | Type of change |
|------|---------------|
| `src/graphs/tools.py` | Rewrite docstrings for 12 existing tools; add 14 new tools |
| `src/graphs/ai_agent.py` | Add 14 new tools to the registered list |
| `src/quality_checks.py` | Add `compute_colorfulness`, `get_visual_metrics` |
| `src/db_service.py` | Add `get_garbage_photos_with_issues`, `get_garbage_photo_paths`, `get_photos_by_tag_id`, `search_photos_by_exif_params`; extend `perform_undo` |
| `tests/test_tool_garbage.py` | New — ~10 tests |
| `tests/test_tool_quality.py` | New — ~13 tests |
| `tests/test_tool_duplicate.py` | New — ~10 tests |
| `tests/test_tool_annotation.py` | New — ~16 tests |
| `tests/test_tool_search.py` | New — ~10 tests |
