# Phase 10 — Prompts Table & Management Page

## Problem Statement

Prompts used by the AI pipeline are currently hard-coded in `prompts/prompts.json` and loaded
once at module import time into a global `PROMPTS` dict. This means:

1. Changes require editing a JSON file and restarting the server.
2. There is no UI to inspect or edit prompts.
3. Prompts are silently stale if `prompts.json` is updated after startup.

## Goal

- Store all `prompts.json` prompts in a DB table called `prompts`.
- Seed the table from `prompts.json` during `install.py` (idempotent — existing rows kept).
- All call sites fetch the prompt text fresh from the DB on every call (no cache).
- Add a **Prompts page** with a sidebar link that lets users view and edit every prompt.

---

## Scope — What Goes in the New Table

Only the prompts currently in `prompts/prompts.json`:

| key | group | Current text |
|-----|-------|-------------|
| `vision_analysis.system_prompt` | vision_analysis | "You are an expert AI visually analyzing photos…" |
| `vision_analysis.describe_scene` | vision_analysis | "Describe this scene in one concise…" |
| `vision_analysis.is_document` | vision_analysis | "Look at this photo and answer only yes or no…" |
| `chat_agent.system_message` | chat_agent | "SYSTEM: You are a photo search engine…" |

**Not in scope**: `TemplateTag.clip_prompt` and `TemplateCategory.clip_prompt` — already managed
via their own pages and tables.

`build_photo_text_for_embedding` in `src/ai/prompts.py` is a Python function/template, not a
stored prompt — it stays as-is.

---

## Architecture

### DB Table — `prompts`

```python
class Prompt(Base):
    __tablename__ = "prompts"
    id          = Column(Integer, primary_key=True, index=True)
    key         = Column(String, unique=True, nullable=False, index=True)  # "vision_analysis.describe_scene"
    group       = Column(String, nullable=False)   # "vision_analysis"
    name        = Column(String, nullable=False)   # "describe_scene"
    title       = Column(String, nullable=False)   # Human-readable label shown in UI
    text        = Column(Text,   nullable=False)   # Editable prompt text
    description = Column(String, nullable=True)    # Optional usage hint shown in UI
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### Fetch Helper — `get_prompt(key, db_path) -> str`

A single function in `src/ai/prompts.py` using **raw sqlite3** (no SQLAlchemy), so it works
from both the FastAPI process and Huey worker processes without circular imports.

Falls back to the JSON file only if the DB file doesn't exist yet (first-run / tests).

```python
def get_prompt(key: str, db_path: str | None = None) -> str:
    """Fetch prompt text from DB. Falls back to prompts.json if DB unavailable."""
    ...
```

All call sites replace `PROMPTS["group"]["name"]` with `get_prompt("group.name")`.

### "No cache" guarantee

`get_prompt()` executes a `SELECT` on every call. SQLite reads are fast (<1 ms) and these
prompts are used on the inference path, not in tight loops.

---

## Call Sites to Update

| File | Current | After |
|------|---------|-------|
| `src/ai/vision.py:22` | `self.system_prompt = PROMPTS["vision_analysis"]["system_prompt"]` | Remove; fetch per call in `generate_vision_text()` |
| `src/ai/vision.py:65-67` | `PROMPTS["vision_analysis"].get(prompt_key, …)` | `get_prompt(f"vision_analysis.{prompt_key}")` |
| `src/model_services.py:230-231` | `PROMPTS["vision_analysis"].get(prompt_key, …)` | `get_prompt(f"vision_analysis.{prompt_key}")` |
| `src/graphs/ai_agent.py:108` | `PROMPTS["chat_agent"]["system_message"]` | `get_prompt("chat_agent.system_message")` |

`context_rag` is defined in the JSON but unused in code — it will live in the DB for future
use and be editable on the Prompts page.

---

## Backend — Files to Create / Modify

### New: DB migration for existing installs

`src/main.py` lifespan (or a new `src/migrate_prompts.py`): run
`CREATE TABLE IF NOT EXISTS prompts (…)` on startup so existing DBs get the table without
breaking.

### 1. `src/models.py`
Add `Prompt` class (schema above). Import `datetime`.

### 2. `src/db_service.py`
Add:
```python
def get_all_prompts(db: Session) -> list[Prompt]
def get_prompt_by_key(db: Session, key: str) -> Prompt | None
def update_prompt(db: Session, key: str, text: str) -> Prompt | None
def seed_prompts_from_json(db: Session, json_path: Path) -> int  # returns count seeded
```

### 3. `src/ai/prompts.py`
- Keep `load_prompts()` (used by `seed_prompts_from_json` and as fallback).
- Keep `PROMPTS` export **temporarily** as fallback while migration runs.
- Add `get_prompt(key: str, db_path: str | None = None) -> str`.
- Keep `build_photo_text_for_embedding` unchanged.

### 4. `src/install.py`
In `run_installation()`, after DB init:
```python
seeded = seed_prompts_from_json(db, PROMPTS_JSON_PATH)
logger.info(f"[install] Prompts seeded: {seeded} new rows")
```

### 5. `src/schemas.py`
```python
class PromptResponse(BaseModel):
    id: int
    key: str
    group: str
    name: str
    title: str
    text: str
    description: str | None
    updated_at: datetime

class PromptUpdate(BaseModel):
    text: str
```

### 6. `src/main.py`
Add:
```
GET  /api/prompts/         → list all prompts (sorted by group, name)
PUT  /api/prompts/{key}    → update prompt text, return updated row
```

Also add table-creation safety in lifespan:
```python
from src.models import Prompt  # ensures table is created by create_all
```

### 7. `src/ai/vision.py`
- Remove `from src.ai.prompts import PROMPTS` and `self.system_prompt = …`.
- In `generate_vision_text()`: fetch system_prompt and prompt_text via `get_prompt()`.

### 8. `src/model_services.py`
- Replace the inline `from src.ai.prompts import PROMPTS` + `PROMPTS[…]` lookup
  with `get_prompt(f"vision_analysis.{prompt_key}")`.

### 9. `src/graphs/ai_agent.py`
- Replace `PROMPTS["chat_agent"]["system_message"]` with
  `get_prompt("chat_agent.system_message")`.
- Remove `from src.ai.prompts import PROMPTS`.

---

## API Endpoints

```
GET  /api/prompts/
  Response: list[PromptResponse]  (all 5 prompts, sorted group → name)

PUT  /api/prompts/{key}
  Body:    { "text": "new prompt text" }
  Response: PromptResponse
  Error:   404 if key not found
```

---

## Frontend — Files to Create / Modify

### 1. `src/types/api.ts`
```typescript
export interface Prompt {
    id: number
    key: string
    group: string
    name: string
    title: string
    text: string
    description: string | null
    updated_at: string
}
```

### 2. `src/api/client.ts`
```typescript
export async function getPrompts(): Promise<Prompt[]>
export async function updatePrompt(key: string, text: string): Promise<Prompt>
```

### 3. `src/pages/PromptsPage.tsx`
- Load all prompts on mount.
- Group by `group` → render a section per group with a heading.
- Each prompt card shows: `title`, optional `description`, and a `<textarea>` for `text`.
- Per-card Save button; saving updates only that one prompt.
- Inline success/error feedback (no modal needed).
- Auto-resize textarea to content.

### 4. `src/pages/PromptsPage.css`
Styling consistent with `ModelsPage.css`.

### 5. `src/components/ui/Sidebar.tsx`
Add link: `{ to: '/prompts', label: 'Prompts', icon: '📝' }` — between Models and Settings.

### 6. `src/pages/AppRoutes.tsx`
Add `<Route path="/prompts" element={<PromptsPage />} />`.

---

## TDD Sequence

### Step 1 — DB layer tests (`tests/test_prompts_db.py`)
Write first:
- `test_seed_creates_all_5_rows`
- `test_seed_is_idempotent`
- `test_get_prompt_by_key_returns_correct_text`
- `test_get_prompt_by_key_unknown_returns_none`
- `test_update_prompt_changes_text`

Then implement `seed_prompts_from_json`, `get_all_prompts`, `get_prompt_by_key`,
`update_prompt` in `db_service.py`.

### Step 2 — `get_prompt()` helper tests (`tests/test_prompts_helper.py`)
Write first:
- `test_get_prompt_reads_from_db`
- `test_get_prompt_falls_back_to_json_when_db_missing`
- `test_get_prompt_unknown_key_raises_or_returns_default`

Then implement `get_prompt()` in `src/ai/prompts.py`.

### Step 3 — API tests (add to `tests/test_main.py`)
Write first:
- `test_get_prompts_returns_all_5`
- `test_update_prompt_changes_text_and_returns_updated`
- `test_update_prompt_unknown_key_returns_404`

Then implement API endpoints in `src/main.py`.

### Step 4 — Integration tests for call sites
Write first:
- `test_call_vision_model_uses_db_prompt` (mock `get_prompt`, verify text passed to LLM)
- `test_ai_agent_uses_db_system_message`

Then update `vision.py`, `model_services.py`, `ai_agent.py`.

---

## Prompt Metadata (seed values)

```json
[
  {
    "key": "vision_analysis.system_prompt",
    "group": "vision_analysis",
    "name": "system_prompt",
    "title": "Vision — System Prompt",
    "description": "Sets the AI persona for all vision analysis tasks. Applied as the system message to the local Qwen model.",
    "text": "You are an expert AI visually analyzing photos. Be concise and precise."
  },
  {
    "key": "vision_analysis.describe_scene",
    "group": "vision_analysis",
    "name": "describe_scene",
    "title": "Vision — Describe Scene",
    "description": "Used when generating a natural-language description of a photo.",
    "text": "Describe this scene in one concise, high-quality sentence focusing on the main action and environment."
  },
  {
    "key": "vision_analysis.is_document",
    "group": "vision_analysis",
    "name": "is_document",
    "title": "Vision — Is Document?",
    "description": "Classifies whether a photo is a text document. Must return only 'yes' or 'no'.",
    "text": "Look at this photo and answer only yes or no if this photo is a text document."
  },
  {
    "key": "chat_agent.system_message",
    "group": "chat_agent",
    "name": "system_message",
    "title": "Chat Agent — System Message",
    "description": "Main system message for the AI photo search agent. Controls tool usage rules and response language.",
    "text": "SYSTEM: You are a photo search engine…"
  },
]
```

---

## Open Questions / Design Decisions

1. **`prompts.json` after migration** — keep as seed source only. DB is the single source of truth.
   The file is no longer read at runtime after the migration is complete.

2. **Vision local model — system_prompt** — currently cached as `self.system_prompt` in
   `QwenVisionGenerator.__init__`. After the change, it is fetched inside
   `generate_vision_text()` on every call. Overhead: one sqlite3 `SELECT` per image (~<1ms).

3. **`PROMPTS` global** — removed from all call sites. Keep `load_prompts()` in `prompts.py`
   only as a utility used by `seed_prompts_from_json`. The `PROMPTS = load_prompts()` export
   can be removed once all call sites are updated.

4. **Huey workers** — `get_prompt()` uses raw sqlite3 so it works identically in worker
   processes without importing SQLAlchemy. The `_DB_PATH` is resolved from `Database_Settings`.

5. **context_rag** — removed. Not wired to any code, not included in the table or UI.

---

## Execution Order

1. Tests: `test_prompts_db.py` → implement DB layer
2. Tests: `test_prompts_helper.py` → implement `get_prompt()`
3. Tests: API tests → implement endpoints
4. Tests: call-site integration tests → update `vision.py`, `model_services.py`, `ai_agent.py`
5. Frontend: types → client → PromptsPage → Sidebar → Routes
6. Run full test suite → commit
