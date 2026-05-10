# Agent Actions — Implementation Plan

> **Goal:** Add photo selection to ChatPage, a DEFAULT_FOLDER setting, five new agent tools
> (create_folder, move_photos, archive_photos, get_action_history, undo_last_action),
> and a persistent action history table with rollback accessible both via API and via the agent.
>
> **Approach:** TDD · Subagent-Driven Development · Backend-first per task

---

## ✅ Design Decisions (All Resolved)

**Q1 — Checkbox scope:** Checkboxes only in **ChatPage left panel** (Related photos). Not on GalleryPage.

**Q2 — Selected IDs to agent:** **Frontend appends IDs to the text message.**
When photos are selected, the frontend adds a line to the user message before sending:
`"\n\n[Selected photo IDs: 1, 2, 3]"`
No changes to `ChatRequest` schema or backend are needed for this.

**Q3 — Rollback semantics:**
- `create_folder` → `rmdir` the folder (only if empty, otherwise return error to agent)
- `move_photos` → move files back to original paths; restore `file_path` in DB; un-archive if this action archived them
- `archive_photos` → **smart zip undo:**
  - Open the zip; compare its contents against `undo_data["added_names"]`
  - If zip contains **only** the added files → delete the whole zip
  - If zip contains **other files too** → remove only the added entries (recreate zip without them)
  - Also set `is_archived=False` in DB for photos that were marked archived by this action

**Q4 — archive_photos + DB:** The tool **marks `is_archived=True`** in DB for each photo (only if not already archived). On undo, only photos that were **newly archived** by this action are un-archived (`is_archived=False`). Photos that were already archived before are left unchanged.

**Q5 — History UI:** **C (both):**
- "↩ Undo" button in ChatPage calls `POST /api/history/undo/`
- Agent tools `get_action_history` and `undo_last_action`

**Q6 — DEFAULT_FOLDER storage:** **DB `app_settings` table** (key-value), `GET/PUT /api/settings/`. SettingsPage already built with localStorage placeholder — will be wired to real API in Task 7.

**Q7 — Path escaping:** **Return clear error message to the agent.** Agent reports it to the user.

---

## Architecture Summary

### New Backend files / changes

| File | Change |
|---|---|
| `backend/src/models.py` | Add `AppSetting`, `HistoryAction` |
| `backend/src/db_service.py` | Add CRUD for both new models |
| `backend/src/main.py` | Add `/api/settings/` and `/api/history/` endpoints |
| `backend/src/graphs/tools.py` | Add `create_folder`, `move_photos`, `archive_photos` tools |
| `backend/src/graphs/ai_agent.py` | Register 5 new tools |
| `backend/src/schemas.py` | Add `AppSettingSchema`, `HistoryActionSchema` |

### New Frontend files / changes

| File | Change |
|---|---|
| `frontend/src/pages/ChatPage.tsx` | Add checkbox state, include photo_ids in sendChat |
| `frontend/src/pages/SettingsPage.tsx` | Add DEFAULT_FOLDER form |
| `frontend/src/api/client.ts` | Add `getSettings`, `updateSetting`, `undoLastAction` |
| `frontend/src/pages/ChatPage.css` | Checkbox styles |

### New DB tables

```sql
CREATE TABLE app_settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
-- Seed: INSERT OR IGNORE INTO app_settings VALUES ('default_folder', '');

CREATE TABLE history_actions (
    id          INTEGER PRIMARY KEY,
    action_type TEXT NOT NULL,   -- create_folder | move_photos | archive_photos
    photo_ids   TEXT,            -- JSON array of int
    params      TEXT NOT NULL,   -- JSON: action-specific params (paths, etc.)
    undo_data   TEXT NOT NULL,   -- JSON: data needed to reverse (original paths, etc.)
    created_at  DATETIME DEFAULT (datetime('now'))
);
```

---

## Task 1 — AppSetting model + API

**Files:** `models.py`, `db_service.py`, `main.py`, `schemas.py`
**Tests:** `backend/tests/test_api_settings.py`

### What to build

```python
# models.py
class AppSetting(Base):
    __tablename__ = "app_settings"
    key   = Column(String, primary_key=True)
    value = Column(String, nullable=False, default="")

# db_service.py
def get_setting(db, key: str) -> Optional[str]
def set_setting(db, key: str, value: str) -> AppSetting
def get_all_settings(db) -> dict[str, str]

# schemas.py
class AppSettingSchema(BaseModel):
    key: str
    value: str

# main.py
GET  /api/settings/            → dict[str, str]
PUT  /api/settings/{key}       → AppSettingSchema   body: {"value": "..."}
```

### Tests (4)
```
test_get_settings_returns_empty_dict_initially
test_set_setting_creates_and_updates_value
test_api_get_settings_returns_200
test_api_put_setting_updates_value
```

---

## Task 2 — HistoryAction model + API + agent tools

**Files:** `models.py`, `db_service.py`, `main.py`, `schemas.py`, `graphs/tools.py`, `graphs/ai_agent.py`
**Tests:** `backend/tests/test_api_history.py`, `backend/tests/test_tool_history.py`

### What to build

```python
# models.py
class HistoryAction(Base):
    __tablename__ = "history_actions"
    id          = Column(Integer, primary_key=True)
    action_type = Column(String, nullable=False)
    photo_ids   = Column(String)           # JSON list[int]
    params      = Column(String, nullable=False)   # JSON
    undo_data   = Column(String, nullable=False)   # JSON
    created_at  = Column(DateTime, default=datetime.utcnow)

# db_service.py
def create_history_action(db, action_type, photo_ids, params, undo_data) -> HistoryAction
def get_history_actions(db, limit: int = 20) -> list[HistoryAction]
def get_last_history_action(db) -> Optional[HistoryAction]
def delete_history_action(db, action_id: int) -> None

# schemas.py
class HistoryActionSchema(BaseModel):
    id: int
    action_type: str
    photo_ids: list[int]
    params: dict
    undo_data: dict
    created_at: datetime

# main.py
GET  /api/history/             → list[HistoryActionSchema]  (last 20 actions)
POST /api/history/undo/        → {"status": "ok", "detail": "..."}
```

The undo logic (shared between API endpoint and agent tool via a service function):
```python
# db_service.py  — reusable, called by both endpoint and agent tool
def perform_undo(db) -> str:
    action = get_last_history_action(db)
    if not action:
        return "No action to undo."
    if action.action_type == "create_folder":
        # rmdir only if empty
    elif action.action_type == "move_photos":
        # move files back, restore DB file_path
    elif action.action_type == "archive_photos":
        # os.remove(zip_path) if exists
    delete_history_action(db, action.id)
    return f"Undone: {action.action_type}"
```

### Agent tools (2 new)

```python
@tool
def get_action_history() -> str:
    """
    Return the last 20 recorded actions (create_folder, move_photos, archive_photos).

    Use this when:
    - The user asks "what did you do?", "show history", "what actions were taken?"

    Returns a human-readable summary of recent actions with their IDs and timestamps.
    """

@tool
def undo_last_action() -> str:
    """
    Undo the most recent recorded action.

    - create_folder  → removes the created directory (only if empty)
    - move_photos    → moves files back to original locations, restores DB paths
    - archive_photos → deletes the created zip file

    Use when:
    - The user says "undo", "undo that", "revert last action", "go back"

    Returns a confirmation of what was undone, or an error if nothing to undo.
    """
```

Both tools are registered in `ai_agent.py` in the main `tools` list.

### Tests (8)
```
test_create_history_action_persists
test_get_history_actions_returns_list
test_get_last_history_action
test_undo_create_folder_removes_directory
test_undo_move_photos_restores_paths
test_undo_archive_photos_deletes_zip
test_undo_returns_error_when_no_history
test_tool_get_action_history_returns_readable_summary
test_tool_undo_last_action_delegates_to_perform_undo
```

---

## Task 3 — create_folder agent tool

**Files:** `graphs/tools.py`, `graphs/ai_agent.py`
**Tests:** `backend/tests/test_tool_folder.py`

### What to build

```python
@tool
def create_folder(folder_name: str, parent_path: str = "") -> str:
    """
    Create a new folder inside the allowed root directory.

    The allowed root is the DEFAULT_FOLDER setting if set, otherwise the user's home directory.
    The folder_name must not contain path separators.
    The parent_path is relative to the allowed root (empty = root itself).

    Returns a success message with the full path created, or an error if the path
    would escape the allowed root or the folder already exists.
    """
```

Internal helper:
```python
def _get_allowed_root(db) -> Path:
    val = get_setting(db, "default_folder")
    root = Path(val) if val else Path.home()
    return root.resolve()

def _safe_resolve(root: Path, relative: str) -> Path:
    """Resolve relative path within root; raise ValueError if it escapes."""
    target = (root / relative).resolve()
    if not str(target).startswith(str(root)):
        raise ValueError(f"Path escapes allowed root: {target}")
    return target
```

History saved:
```json
{
  "action_type": "create_folder",
  "params": {"path": "/absolute/path/to/new_folder"},
  "undo_data": {"path": "/absolute/path/to/new_folder"}
}
```

### Tests (5)
```
test_create_folder_inside_allowed_root
test_create_folder_with_parent_path
test_create_folder_escaping_root_raises_error
test_create_folder_already_exists_returns_error
test_create_folder_saves_history_action
```

---

## Task 4 — move_photos agent tool

**Files:** `graphs/tools.py`, `graphs/ai_agent.py`
**Tests:** `backend/tests/test_tool_folder.py` (appended)

### What to build

```python
@tool
def move_photos(photo_ids: List[int], destination_folder: str) -> str:
    """
    Move photos (by ID) to a destination folder within the allowed root.

    destination_folder is relative to the allowed root.
    DB file_path is updated for each moved photo.
    Original paths are saved in history for rollback.

    Returns a summary of moved files or an error.
    """
```

Logic:
1. Validate `destination_folder` is inside allowed root
2. Load each photo from DB; skip missing IDs with a warning
3. `shutil.move(photo.file_path, dest / filename)`
4. Update `photo.file_path` in DB
5. Save `HistoryAction` with `undo_data = {"original_paths": {id: old_path, ...}}`

### Tests (5)
```
test_move_photos_updates_file_path_in_db
test_move_photos_saves_history_action
test_move_photos_destination_escapes_root_returns_error
test_move_photos_missing_photo_id_skipped
test_move_photos_creates_destination_if_not_exists
```

---

## Task 5 — archive_photos agent tool

**Files:** `graphs/tools.py`, `graphs/ai_agent.py`, `db_service.py`
**Tests:** `backend/tests/test_tool_archive.py`

### What to build

```python
@tool
def archive_photos(photo_ids: List[int]) -> str:
    """
    Zip the specified photos into MyPhotoArchive.zip inside the allowed root
    and mark each photo as archived in the database.

    - Allowed root = DEFAULT_FOLDER setting, or user home directory if not set.
    - If MyPhotoArchive.zip already exists, new files are appended (not overwritten).
    - Only photos not yet marked is_archived=True are newly archived; already-archived
      photos are included in the zip but their DB status is not changed again.
    - Saves a history action recording which files were added and which photo IDs
      were newly marked archived, enabling precise undo.

    Returns: path to the zip and count of photos added.
    """
```

Logic:
1. Get allowed root from `app_settings`
2. `zip_path = root / "MyPhotoArchive.zip"`
3. Open with `zipfile.ZipFile(zip_path, "a")` (append mode)
4. For each photo ID:
   - Load from DB; skip if not found
   - Add file to zip; track `added_names` (arcnames)
   - If `photo.is_archived` is False → set `True`, track in `newly_archived_ids`
5. `db.commit()`
6. Save `HistoryAction`:
```json
{
  "action_type": "archive_photos",
  "photo_ids": [1, 2, 3],
  "params": {"zip_path": "/home/user/Photos/MyPhotoArchive.zip"},
  "undo_data": {
    "zip_path": "/home/user/Photos/MyPhotoArchive.zip",
    "added_names": ["photo1.jpg", "photo2.jpg"],
    "newly_archived_ids": [1, 3]
  }
}
```

**Undo logic for `archive_photos`** (in `perform_undo`):
```python
zip_path = Path(undo_data["zip_path"])
added_names = set(undo_data["added_names"])
if zip_path.exists():
    with zipfile.ZipFile(zip_path) as zf:
        all_names = set(zf.namelist())
    remaining = all_names - added_names
    if not remaining:
        zip_path.unlink()          # only our files → delete zip
    else:
        # recreate zip without added_names
        tmp = zip_path.with_suffix(".tmp.zip")
        with zipfile.ZipFile(zip_path) as src, zipfile.ZipFile(tmp, "w") as dst:
            for name in src.namelist():
                if name not in added_names:
                    dst.writestr(name, src.read(name))
        tmp.replace(zip_path)
# un-archive only the newly archived photos
for pid in undo_data["newly_archived_ids"]:
    photo = get_photo_by_id(db, pid)
    if photo:
        photo.is_archived = False
db.commit()
```

### Tests (6)
```
test_archive_photos_creates_zip
test_archive_photos_appends_to_existing_zip
test_archive_photos_marks_is_archived_in_db
test_archive_photos_skips_already_archived_status
test_archive_photos_saves_history_with_newly_archived_ids
test_archive_photos_skips_missing_files
```

---

## Task 6 — ChatPage: inject selected IDs into message text (frontend only)

**Files:** `frontend/src/pages/ChatPage.tsx`
**No backend changes required** — IDs travel as part of the plain message string.

### What to build

When the user clicks Send and at least one photo is checked, the frontend appends
a line to the message before calling `sendChat`:

```ts
const finalMessage = selectedPhotoIds.size > 0
    ? `${input.trim()}\n\n[Selected photo IDs: ${[...selectedPhotoIds].join(', ')}]`
    : input.trim()

await sendChat({ message: finalMessage, thread_id: threadId ?? undefined })
```

The agent sees the IDs naturally in the conversation and can pass them directly to
`move_photos`, `archive_photos`, etc.

### Tests (2, part of ChatPage tests in Task 8)
```
test_sends_plain_message_when_no_photos_selected
test_appends_photo_ids_to_message_when_photos_selected
```

---

## Task 7 — SettingsPage with DEFAULT_FOLDER form

**Files:** `frontend/src/pages/SettingsPage.tsx`, `frontend/src/api/client.ts`
**Tests:** `frontend/src/pages/__tests__/SettingsPage.test.tsx`

### What to build

```ts
// client.ts
export interface AppSettings { [key: string]: string }
export async function getSettings(): Promise<AppSettings>
export async function updateSetting(key: string, value: string): Promise<void>
```

```tsx
// SettingsPage.tsx — minimal form
export function SettingsPage() {
    const [defaultFolder, setDefaultFolder] = useState('')
    const [saved, setSaved] = useState(false)

    useEffect(() => {
        getSettings().then(s => setDefaultFolder(s['default_folder'] ?? ''))
    }, [])

    async function handleSave() {
        await updateSetting('default_folder', defaultFolder)
        setSaved(true)
    }

    return (
        <div className="settings-page">
            <h1>Settings</h1>
            <label>
                Default folder
                <input value={defaultFolder} onChange={e => setDefaultFolder(e.target.value)} />
            </label>
            <button onClick={handleSave}>Save</button>
            {saved && <span>Saved</span>}
        </div>
    )
}
```

### Tests (3)
```
test_settings_page_renders_default_folder_input
test_settings_page_loads_existing_value
test_settings_page_save_calls_update_setting
```

---

## Task 8 — ChatPage checkboxes + selected IDs in sendChat

**Files:** `frontend/src/pages/ChatPage.tsx`, `frontend/src/pages/ChatPage.css`,
           `frontend/src/api/client.ts`
**Tests:** `frontend/src/pages/__tests__/ChatPage.test.tsx`

### What to build

```tsx
// ChatPage.tsx additions
const [selectedPhotoIds, setSelectedPhotoIds] = useState<Set<number>>(new Set())

function togglePhoto(id: number) {
    setSelectedPhotoIds(prev => {
        const next = new Set(prev)
        next.has(id) ? next.delete(id) : next.add(id)
        return next
    })
}

// Reset selections when agent returns new photos
useEffect(() => { setSelectedPhotoIds(new Set()) }, [contextPhotos])

// In left panel — wrap each PhotoCard in a label with checkbox
<label key={photo.id} className="chat-photo-item">
    <input
        type="checkbox"
        className="chat-photo-item__checkbox"
        checked={selectedPhotoIds.has(photo.id)}
        onChange={() => togglePhoto(photo.id)}
    />
    <PhotoCard photo={photo} />
</label>

// In onSend — include selected IDs
const res = await sendChat({
    message: input,
    thread_id: threadId ?? undefined,
    photo_ids: [...selectedPhotoIds],   // ← NEW
})
```

```ts
// client.ts — extend ChatParams
export interface ChatParams {
    message: string
    thread_id?: string
    photo_ids?: number[]   // ← NEW
}
```

### Tests (4)
```
test_chat_page_shows_checkbox_on_context_photo
test_chat_page_toggles_selection_on_checkbox_click
test_chat_page_sends_selected_photo_ids_with_message
test_chat_page_clears_selection_when_new_photos_arrive
```

---

## Task 9 — Undo button in ChatPage

**Files:** `frontend/src/pages/ChatPage.tsx`, `frontend/src/api/client.ts`
**Tests:** `frontend/src/pages/__tests__/ChatPage.test.tsx` (appended)

### What to build

```ts
// client.ts
export async function undoLastAction(): Promise<{ status: string; detail: string }>
```

```tsx
// ChatPage.tsx — add undo button near input bar
<button
    className="chat-page__undo-btn"
    onClick={handleUndo}
    title="Undo last action"
>
    ↩ Undo
</button>
```

### Tests (2)
```
test_undo_button_is_visible_in_chat_input_area
test_undo_button_calls_undo_api_and_shows_result_in_chat
```

---

## File Map

**Create:**
- `backend/tests/test_api_settings.py`
- `backend/tests/test_api_history.py`
- `backend/tests/test_tool_folder.py`
- `backend/tests/test_tool_archive.py`
- `backend/tests/test_tool_history.py`
- `frontend/src/pages/__tests__/SettingsPage.test.tsx`
- `frontend/src/pages/__tests__/ChatPage.test.tsx`

**Modify:**
- `backend/src/models.py`
- `backend/src/db_service.py`
- `backend/src/schemas.py`
- `backend/src/main.py`
- `backend/src/graphs/tools.py`        — 5 new tools: create_folder, move_photos, archive_photos, get_action_history, undo_last_action
- `backend/src/graphs/ai_agent.py`     — register 5 new tools
- `frontend/src/pages/ChatPage.tsx`
- `frontend/src/pages/ChatPage.css`
- `frontend/src/pages/SettingsPage.tsx`
- `frontend/src/api/client.ts`

---

## Execution Order

| Task | Scope | Depends on | Notes |
|---|---|---|---|
| 1 — AppSetting model + API | Backend | — | Needed by Tools 3,4,5 and Task 7 |
| 2 — HistoryAction model + API + agent tools | Backend | — | Needed by Tools 3,4,5 and Task 9 |
| 3 — create_folder tool | Backend | 1, 2 | — |
| 4 — move_photos tool | Backend | 1, 2 | — |
| 5 — archive_photos tool | Backend | 1, 2 | — |
| 6 — ChatPage: inject IDs into message | Frontend | — | Pure frontend, no backend change |
| 7 — SettingsPage wire to real API | Frontend | 1 | Removes localStorage placeholder |
| 8 — ChatPage checkboxes | Frontend | — | Includes Task 6 logic |
| 9 — Undo button in ChatPage | Frontend | 2 | Calls POST /api/history/undo/ |

**Parallel batches:**
- Batch A (start immediately): Task 1 + Task 2
- Batch B (after A): Task 3 + Task 4 + Task 5
- Batch C (after A, independent of B): Task 6 + Task 7 + Task 8 + Task 9
