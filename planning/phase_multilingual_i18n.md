# Phase: Multilingual Support (i18n)

## Goal

Add full multilingualism to PhotoRAG: English, Russian, Spanish at launch, extensible to future
languages. All UI text is translated. Semantic search works in any language (query translated
to English before embedding). Photo descriptions are stored in English and translated on
processing. OCR text stays in source language for display but is translated to English before
embedding.

## Decisions Made

| Question | Decision |
|---|---|
| Language on switch for old photos | Re-translate all in background (Option A), overwrite `translated_description` |
| macOS first launch | Add Step 0 "Choose Language" to SetupWizard |
| Chat AI | Inject current language into system prompt so AI responds in selected language |
| OCR text translation | Stay in source language for display; translate to English only for embedding |
| Installer language propagation | NSIS writes `bootstrap.json` → backend reads on first startup |
| Frontend i18n library | `react-i18next` + `i18next` |
| "PhotoRAG" brand name | Never translated — stays as-is everywhere |

## Architecture Overview

### Frontend
```
src/i18n/
  index.ts              — i18next init, reads language from settings API
  locales/
    en.json             — source of truth for all translation keys
    ru.json             — Russian strings
    es.json             — Spanish strings
```
- `react-i18next` wraps `App.tsx` via `I18nextProvider`
- `useTranslation()` hook in every component
- Language is initialized from `GET /api/settings/` → `default_language`
- Changing language: (1) updates i18next locale, (2) calls `PUT /api/settings/default_language`,
  (3) triggers batch re-translation API call

### Backend
- `translator.py`: language-agnostic direction logic (supports any pair via `LANG_DICT`)
- `LANG_DICT` extended with `es: "spa_Latn"` (and trivially extensible)
- Batch re-translation: dedicated pipeline (`retranslation_pipeline.py`) that creates
  `PipelineTask` rows per photo — visible on Processing Page like any other pipeline job
- Chat system prompt: language injected at request time
- OCR embedding: translate OCR text to English before embedding if needed

### NSIS Installer (Windows)
- `multiLanguageInstaller: true`, `installerLanguages: [English, Russian, SpanishInternational]`
- Custom NSI include captures `$LANGUAGE` code after user selects
- Maps NSIS code → app code (e.g. `2052 → ru`)
- Writes `%APPDATA%\PhotoRAG\bootstrap.json` with `{ "default_language": "ru" }`
- Backend: on first startup, reads `bootstrap.json` if `default_language` not yet in DB

---

## Phase 8.1 — Backend: Generalize Translator + Add Spanish

### Problem
`translator.py` hardcodes `if DEFAULT_LANGUAGE == "en" / elif == "ru"` direction logic in
`__init__`. This makes adding any new language require modifying the constructor. It also only
supports a single "active" target language baked in at model-load time.

### TDD Tests (write first)
File: `backend/tests/test_translator.py`

```python
def test_lang_dict_has_spanish():
    assert "es" in Translator.LANG_DICT

def test_translate_to_spanish_forward(mock_translator):
    # forward=False, target_lang="es" → src=eng_Latn, tgt=spa_Latn
    mock_translator.translate("Hello", backward=False, target_lang="es")
    # assert tokenizer called with correct src/tgt pair

def test_translate_backward_from_spanish(mock_translator):
    # backward=True, any → English
    result = mock_translator.translate("Hola", backward=True)
    # assert tgt_lang == "eng_Latn"

def test_translate_unknown_lang_falls_back_to_english(mock_translator):
    # target_lang="zh" not in LANG_DICT → fall back, no crash
    mock_translator.translate("text", backward=False, target_lang="zh")
```

### Changes
**`backend/src/ai/translator.py`**
- Remove hardcoded `__init__` direction assignments (no more `if DEFAULT_LANGUAGE == "en"`)
- `translate(text, backward=False, target_lang=None)`:
  - `backward=True` → always `src=<detected or "any">`, `tgt=eng_Latn`
  - `backward=False, target_lang` in LANG_DICT → `src=eng_Latn`, `tgt=LANG_DICT[target_lang]`
  - `backward=False, target_lang` not in LANG_DICT → log warning, return text unchanged
- Add `es: "spa_Latn"` to `LANG_DICT`
- Remove dependency on `Main_Settings.DEFAULT_LANGUAGE` in translator constructor

**`backend/src/config.py`**
- Add `"es"` to list of valid language codes in validation (if any)

**`backend/src/tasks/translation_tasks.py`**
- `_get_target_language()` already reads from DB — no change needed here
- Ensure `translate_description_task` passes `target_lang` correctly (it already does)

---

## Phase 8.2 — Backend: OCR Text Translated to English for Embedding

### Problem
OCR text is extracted in the source language. For semantic search to work, it should be
embedded in English. Display stays in the original extracted language.

### TDD Tests
File: `backend/tests/test_embedding_pipeline.py`

```python
async def test_ocr_embedding_translates_to_english_when_lang_is_russian(mock_translation, mock_embedding):
    # Given: OCR text in Russian, default_language=ru
    # When: embedding pipeline processes OCR text
    # Then: translation call made with backward=True, embedding uses translated text

async def test_ocr_embedding_no_translation_when_lang_is_english(mock_embedding):
    # Given: default_language=en
    # When: embedding pipeline processes OCR text
    # Then: no translation call made, embedding uses raw OCR text
```

### Changes
Find where OCR text enters the embedding pipeline (likely `embedding_queue.py` or
`incoming_pipeline.py`). Before calling `call_embedding_model(text=ocr_text)`, check if
`default_language != "en"` and if so, call `call_translation_model(ocr_text, backward=True)`.

This mirrors the existing pattern in `db_service.py:190-192` for search queries.

---

## Phase 8.3 — Backend: Re-Translation Pipeline

### Problem
When the user switches language, all existing `translated_description` values are in the
old language. We need to re-translate every photo. This must be visible on the Processing
Page as individual per-photo tasks — not a silent background job.

### Design
A new dedicated pipeline (`retranslation_pipeline.py`) mirrors the structure of
`incoming_pipeline.py`. It uses the **same** `PipelineTask` table and `pipeline_tracker`
infrastructure, with a new phase name `"retranslation"`. Each photo gets one task row:
`translate_description_task`. The Processing Page already polls for pending/running tasks,
so retranslation tasks appear there automatically, alongside any other active pipeline work.

```
User changes language → PUT /api/settings/default_language
                      → POST /api/translation/retranslate-all
                      → retranslation_pipeline.start_retranslation(new_lang)
                           ├─ fetch all photo IDs with a description
                           ├─ for each: init_pipeline_tasks(photo_id, "retranslation", [...])
                           └─ run with same concurrency limiter as run_pipelines_batch
                                └─ translate_description_task (via translation_queue)
                                     └─ track_task(photo_id, "retranslation", "translate_description_task")
                                          └─ overwrites translated_description
```

Key distinction from normal pipeline:
- Phase name is `"retranslation"` (not `"phase_2"`) — no collision with ongoing ingestion
- Skipped entirely when `new_lang == "en"` (description IS the text)
- `translate_description_task` already uses `track_task` — we just change the phase argument

### TDD Tests
File: `backend/tests/test_retranslation_pipeline.py`

```python
async def test_retranslation_skips_when_english(mock_db, mock_init_tasks):
    await start_retranslation("en")
    mock_init_tasks.assert_not_called()

async def test_retranslation_creates_pipeline_tasks_per_photo(mock_db_with_3_photos, mock_init_tasks, mock_translate):
    await start_retranslation("es")
    assert mock_init_tasks.call_count == 3
    for call in mock_init_tasks.call_args_list:
        assert call.args[1] == "retranslation"
        assert "translate_description_task" in call.args[2]

async def test_retranslation_tasks_tracked_in_pipeline_tracker(mock_db_with_1_photo, mock_translate):
    await start_retranslation("ru")
    task = PipelineTask.query.filter_by(phase="retranslation").first()
    assert task.status in ("done", "running", "pending")

async def test_retranslation_overwrites_translated_description(mock_db, mock_nllb):
    photo = make_photo(description="A cat", translated_description="Кот")
    await start_retranslation("es")
    assert photo.translated_description == "<Spanish translation of 'A cat'>"

def test_retranslate_all_endpoint_starts_pipeline(client):
    # POST /api/translation/retranslate-all → 202, pipeline task enqueued
    resp = client.post("/api/translation/retranslate-all")
    assert resp.status_code == 202
    assert resp.json()["status"] == "started"
```

### New File: `backend/src/retranslation_pipeline.py`

```python
"""
Re-translation pipeline.

Triggered when the user changes the UI language. Translates every photo's
description to the new language and shows progress on the Processing Page
via the standard PipelineTask / pipeline_tracker mechanism.
"""
_RETRANSLATION_TASKS = ["translate_description_task"]

async def start_retranslation(new_lang: str, max_concurrent: int = 4) -> None:
    if new_lang == "en":
        return  # description column is always English; no translation needed

    db = SessionLocal()
    try:
        photo_ids = db.execute(
            text("SELECT id FROM photos WHERE description IS NOT NULL")
        ).scalars().all()
    finally:
        db.close()

    if not photo_ids:
        return

    semaphore = asyncio.Semaphore(max_concurrent)

    async def _translate_one(photo_id: int) -> None:
        async with semaphore:
            init_pipeline_tasks(photo_id, "retranslation", _RETRANSLATION_TASKS)
            await translate_description_task_for_retranslation(photo_id, new_lang)

    await asyncio.gather(*[_translate_one(pid) for pid in photo_ids])
```

### Update: `backend/src/tasks/translation_tasks.py`
The existing `translate_description_task(photo_id)` is hardcoded to `"phase_2"` as the
tracker phase. Add a sibling function that accepts the phase as a parameter:

```python
async def translate_description_task_for_retranslation(photo_id: int, target_lang: str) -> None:
    async with track_task(photo_id, "retranslation", "translate_description_task"):
        description = await asyncio.to_thread(_get_description_sync, photo_id)
        if not description:
            return
        translated = await call_translation_model(description, backward=False, target_lang=target_lang)
        await asyncio.to_thread(_save_translation_sync, photo_id, translated)
```

### New API Endpoint in `main.py`
```python
@app.post("/api/translation/retranslate-all", status_code=202)
async def trigger_retranslate_all(background_tasks: BackgroundTasks, db: Session):
    """Start the retranslation pipeline for all photos in the selected language."""
    new_lang = get_setting(db, "default_language") or "en"
    background_tasks.add_task(start_retranslation, new_lang)
    return {"status": "started", "language": new_lang}
```

No separate status endpoint needed — the Processing Page already shows all active
`PipelineTask` rows including those with `phase="retranslation"`.

---

## Phase 8.4 — Backend: Chat AI Language Injection

### Problem
Chat AI always responds in English regardless of app language setting.

### TDD Tests
File: `backend/tests/test_chat.py`

```python
def test_chat_system_prompt_includes_language_when_russian(client, mock_settings_ru):
    # POST /api/chat/ with default_language=ru
    # Verify the prompt sent to LLM contains language instruction in Russian

def test_chat_system_prompt_no_language_override_when_english(client, mock_settings_en):
    # POST /api/chat/ with default_language=en
    # No language instruction injected (English is default for most LLMs)
```

### Changes
In the chat endpoint (or system prompt builder), read `default_language` from settings and
append a language instruction when it is not English:

```python
LANG_INSTRUCTION = {
    "ru": "Отвечай на русском языке.",
    "es": "Responde en español.",
}
if lang in LANG_INSTRUCTION:
    system_prompt += f"\n\n{LANG_INSTRUCTION[lang]}"
```

---

## Phase 8.5 — Frontend: i18n Infrastructure

### TDD Tests (write first)
File: `frontend/src/i18n/__tests__/completeness.test.ts`

```typescript
import en from '../locales/en.json'
import ru from '../locales/ru.json'
import es from '../locales/es.json'

function getAllKeys(obj: object, prefix = ''): string[] {
    return Object.entries(obj).flatMap(([k, v]) =>
        typeof v === 'object' ? getAllKeys(v, `${prefix}${k}.`) : [`${prefix}${k}`]
    )
}

test('ru has all keys from en', () => {
    const missing = getAllKeys(en).filter(k => !getAllKeys(ru).includes(k))
    expect(missing).toEqual([])
})

test('es has all keys from en', () => {
    const missing = getAllKeys(en).filter(k => !getAllKeys(es).includes(k))
    expect(missing).toEqual([])
})

test('no extra keys in ru', () => {
    const extra = getAllKeys(ru).filter(k => !getAllKeys(en).includes(k))
    expect(extra).toEqual([])
})

test('no extra keys in es', () => {
    const extra = getAllKeys(es).filter(k => !getAllKeys(en).includes(k))
    expect(extra).toEqual([])
})
```

### Install
```sh
npm install react-i18next i18next
```

### New Files

**`frontend/src/i18n/index.ts`**
```typescript
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from './locales/en.json'
import ru from './locales/ru.json'
import es from './locales/es.json'

export const SUPPORTED_LANGUAGES = [
    { code: 'en', label: 'English' },
    { code: 'ru', label: 'Русский' },
    { code: 'es', label: 'Español' },
]

i18n.use(initReactI18next).init({
    resources: { en: { translation: en }, ru: { translation: ru }, es: { translation: es } },
    lng: 'en',               // overridden at startup from settings API
    fallbackLng: 'en',
    interpolation: { escapeValue: false },
})

export default i18n
```

**`frontend/src/i18n/locales/en.json`** — see Phase 8.6 for full key list

**`frontend/src/main.tsx`** (or `App.tsx`) — import `i18n` (side-effect import) and wrap with
`I18nextProvider` if needed (react-i18next v14 auto-detects)

**Language initialization in `App.tsx`**:
```typescript
// On mount: fetch settings, set i18n language
useEffect(() => {
    getSettings().then(s => {
        if (s.default_language) i18n.changeLanguage(s.default_language)
    })
}, [])
```

---

## Phase 8.6 — Frontend: Translate All UI Strings

### Approach
1. Go page-by-page and component-by-component
2. Extract every user-visible string into `en.json` under the appropriate namespace
3. Replace with `const { t } = useTranslation()` and `t('key')`
4. Add Russian and Spanish translations

### Translation Key Structure (`en.json`)
```json
{
  "common": {
    "save": "Save",
    "cancel": "Cancel",
    "delete": "Delete",
    "confirm": "Confirm",
    "loading": "Loading...",
    "error": "Error",
    "success": "Success",
    "back": "Back",
    "close": "Close",
    "search": "Search",
    "filter": "Filter",
    "reset": "Reset",
    "apply": "Apply",
    "yes": "Yes",
    "no": "No",
    "noResults": "No results found",
    "retry": "Retry"
  },
  "nav": {
    "gallery": "Gallery",
    "search": "Semantic Photo Search",
    "documents": "Documents",
    "chat": "Chat AI",
    "processing": "Video Processing",
    "watchers": "Watchers",
    "models": "Models",
    "settings": "Settings"
  },
  "sidebar": { ... },
  "gallery": {
    "title": "Gallery",
    "empty": "No photos yet",
    "filters": { "date": "Date", "category": "Category", "tag": "Tag", "camera": "Camera", "location": "Location" },
    "sort": { ... }
  },
  "search": {
    "placeholder": "Search photos by meaning...",
    "hint": "Try describing what you're looking for",
    "noResults": "No matching photos found",
    "results": "{{count}} results"
  },
  "photoDetail": { ... },
  "photoEdit": { ... },
  "documents": { ... },
  "chat": {
    "placeholder": "Ask about your photos...",
    "send": "Send",
    "clear": "Clear chat"
  },
  "processing": { ... },
  "watchers": { ... },
  "models": { ... },
  "settings": {
    "title": "Settings",
    "language": "Language",
    "languageHint": "All UI text and AI responses will switch to the selected language. Existing photo descriptions will be re-translated in the background.",
    "defaultFolder": "Default photo folder",
    "save": "Save settings"
  },
  "setupWizard": {
    "chooseLanguage": "Choose your language",
    "chooseLanguageHint": "You can change this later in Settings",
    "continue": "Continue",
    "welcome": { ... },
    "installDeps": { ... },
    "done": { ... }
  },
  "duplicates": { ... },
  "banners": {
    "tesseract": { ... },
    "pipelineWarning": { ... },
    "embeddingReindex": { ... }
  },
  "errors": {
    "generic": "Something went wrong",
    "networkError": "Cannot connect to the backend"
  }
}
```

### TDD Tests Per Component
For each page/component, write a test that:
1. Renders with i18n in a specific language
2. Asserts the translated string appears (not the key)

Example:
```typescript
// gallery.test.tsx
test('gallery empty state shows translated text', () => {
    i18n.changeLanguage('ru')
    render(<GalleryPage />)
    expect(screen.getByText('Нет фотографий')).toBeInTheDocument()
})
```

### Scope — All files requiring changes
**Pages:** GalleryPage, SearchPage, DocumentsPage, ChatPage, SettingsPage, PhotoDetailPage,
PhotoEditPage, JobProcessingPage, FoldersPage, ModelsPage, DuplicatesPage,
GarbageBadPhotoPage, TemplateTagsPage, TemplateCategoriesPage, PromptsPage

**Components:** Header, Sidebar, SearchBar, FilterBar, EmptyState, ConfirmModal,
FolderSelector, DateFilterButton, CategoriesFilterButton, TagsFilterButton,
CamerasFilterButton, GeopositionsFilterButton, TesseractBanner, PipelineWarningBanner,
EmbeddingReindexBanner, PhotoCard, CategoryPickerModal, TagPickerModal

**SetupWizard steps:** StepWelcome, StepModelPicker, StepModelConfig, StepInstallDeps,
StepDownloading, StepInitDb, StepDone (+ new StepLanguage)

---

## Phase 8.7 — Frontend: SetupWizard Language Step (Step 0)

### Purpose
On first launch (macOS and Windows), the SetupWizard runs. Step 0, before StepWelcome,
is a language picker. After the user selects, i18n switches immediately so all subsequent
steps display in the chosen language. The selection is saved via `PUT /api/settings/default_language`
when continuing from Step 0.

### TDD Tests
```typescript
test('step 0 renders language options in their own languages', () => {
    render(<SetupWizard onComplete={vi.fn()} />)
    expect(screen.getByText('English')).toBeInTheDocument()
    expect(screen.getByText('Русский')).toBeInTheDocument()
    expect(screen.getByText('Español')).toBeInTheDocument()
})

test('selecting Russian updates i18n immediately', async () => {
    render(<SetupWizard onComplete={vi.fn()} />)
    await userEvent.click(screen.getByText('Русский'))
    // subsequent text is in Russian
    expect(screen.getByText('Продолжить')).toBeInTheDocument()
})
```

### New File: `frontend/src/pages/SetupWizard/StepLanguage.tsx`
```typescript
export function StepLanguage({ onContinue }: { onContinue: () => void }) {
    // Display each language option in its OWN language (not translated)
    // On select: i18n.changeLanguage(code), save to settings API
    // "Continue" button label IS translated (already switched)
}
```

### Changes to `SetupWizard/index.tsx`
- Insert `'language'` as the first step in the step sequence
- Step 0 does not show a back button

---

## Phase 8.8 — Frontend: Language Change Triggers Re-Translation Pipeline

### Changes to `SettingsPage.tsx`
When `default_language` changes and is saved:
1. Call `PUT /api/settings/default_language` (existing)
2. If new language ≠ `"en"`, call `POST /api/translation/retranslate-all`
3. Show a one-time toast/banner (not polling):
   > "Description translation started. Track progress on the Processing page."
   — with a direct link to `/processing`
4. No polling needed — the Processing Page already shows per-photo task status

This is intentionally minimal on the Settings side. The Processing Page is the
single source of truth for all background work, including retranslation.

### TDD Tests
```typescript
test('changing language to Russian triggers retranslate-all API call', async () => {
    const retranslate = vi.fn().mockResolvedValue({ status: 'started' })
    // select Russian → save → verify retranslate called once
})

test('banner with Processing page link appears after language change', async () => {
    // select Spanish → save
    // expect: toast/banner visible containing a link to /processing
    // expect: no polling calls to /api/translation/status
})

test('retranslate-all not called when switching back to English', async () => {
    // start in Russian, select English → save
    // expect: retranslate-all endpoint NOT called
})
```

### Processing Page: retranslation phase visibility
The Processing Page reads `PipelineTask` rows from `GET /api/pipeline/tasks` (or equivalent).
Retranslation tasks have `phase = "retranslation"` and `task_name = "translate_description_task"`.

If the Processing Page currently only shows certain phase names, ensure `"retranslation"` is
included — or better, show all phases without an allowlist. Each retranslation row should
display the photo thumbnail (if available), phase label "Translation", task name, and status.

No new backend endpoint is needed — the existing pipeline task API already returns these rows.

---

## Phase 8.9 — NSIS Installer: Language Selector + Bootstrap

### electron-builder config changes (`package.json`)
```json
"nsis": {
    "multiLanguageInstaller": true,
    "installerLanguages": ["English", "Russian", "SpanishInternational"],
    "include": "build/installer.nsh",
    ...existing options...
}
```

### New File: `frontend/build/installer.nsh`
Custom NSIS script included into the installer. Runs after installation completes.
Maps NSIS `$LANGUAGE` code to app language code, writes bootstrap file:

```nsis
!macro customInstall
    ; Map NSIS language ID to app language code
    StrCpy $0 "en"
    ${If} $LANGUAGE == 1049      ; Russian
        StrCpy $0 "ru"
    ${ElseIf} $LANGUAGE == 3082  ; Spanish (International)
        StrCpy $0 "es"
    ${EndIf}

    ; Write bootstrap.json to %APPDATA%\PhotoRAG\
    CreateDirectory "$APPDATA\PhotoRAG"
    FileOpen $1 "$APPDATA\PhotoRAG\bootstrap.json" w
    FileWrite $1 '{"default_language":"$0"}'
    FileClose $1
!macroend
```

### Backend: Read Bootstrap on First Startup
In `backend/src/main.py` startup (lifespan):

```python
def _apply_bootstrap_settings(db):
    """Read bootstrap.json written by the NSIS installer and apply to DB settings."""
    bootstrap_path = data_dir() / "bootstrap.json"
    if not bootstrap_path.exists():
        return
    try:
        data = json.loads(bootstrap_path.read_text())
        lang = data.get("default_language", "en")
        # Only apply if not already set (truly first launch)
        if not get_setting(db, "default_language"):
            set_setting(db, "default_language", lang)
            logger.info(f"[bootstrap] Applied language from installer: {lang}")
        bootstrap_path.unlink()  # consume once
    except Exception as e:
        logger.warning(f"[bootstrap] Failed to apply: {e}")
```

### TDD Tests
```python
def test_bootstrap_applies_language_on_first_launch(tmp_path, mock_db):
    bootstrap = tmp_path / "bootstrap.json"
    bootstrap.write_text('{"default_language":"ru"}')
    _apply_bootstrap_settings(mock_db)
    assert get_setting(mock_db, "default_language") == "ru"

def test_bootstrap_file_deleted_after_applying(tmp_path, mock_db):
    bootstrap = tmp_path / "bootstrap.json"
    bootstrap.write_text('{"default_language":"es"}')
    _apply_bootstrap_settings(mock_db)
    assert not bootstrap.exists()

def test_bootstrap_skipped_if_language_already_set(tmp_path, mock_db_with_language):
    bootstrap = tmp_path / "bootstrap.json"
    bootstrap.write_text('{"default_language":"ru"}')
    _apply_bootstrap_settings(mock_db_with_language)
    # existing setting not overwritten
    assert get_setting(mock_db_with_language, "default_language") == "en"
```

---

## Phase 8.10 — Integration Tests

### Frontend E2E (Playwright)
```typescript
test('switch language to Russian — UI updates immediately', async ({ page }) => {
    await page.goto('/')
    await page.click('[data-testid="nav-settings"]')
    await page.selectOption('[data-testid="language-select"]', 'ru')
    await page.click('[data-testid="save-settings"]')
    // Header now shows Russian nav label
    await expect(page.locator('[data-testid="nav-gallery"]')).toHaveText('Галерея')
})

test('semantic search in Russian translates query to English', async ({ page }) => {
    // Intercept POST /api/search/ and verify the body's text_query
    // is in English (not Russian) after language switch
})
```

### Backend Integration
```python
async def test_full_translation_pipeline_es(client, mock_db, mock_nllb):
    # 1. Set language to es
    # 2. Process photo description "A sunny beach"
    # 3. Verify translated_description populated in Spanish
    # 4. Search "playa soleada" → verify query translated to English before embedding
```

---

## Implementation Order (recommended)

```
8.1  Backend: Translator generalization + Spanish     ← unblocks everything else
8.2  Backend: OCR embedding translation               ← independent, small
8.3  Backend: Batch re-translation + status API       ← needed by 8.8
8.4  Backend: Chat AI language injection              ← independent, small
8.5  Frontend: i18n infrastructure                   ← unblocks all frontend phases
8.6  Frontend: Translate all strings                  ← largest phase, can be done in parallel per page
8.7  Frontend: SetupWizard language step              ← depends on 8.5
8.8  Frontend: Language change → re-translation       ← depends on 8.3 + 8.5
8.9  NSIS: Installer language selector + bootstrap    ← depends on 8.3 (backend bootstrap)
8.10 Integration tests                                ← last
```

## Files Created / Modified

### Backend (new)
- `backend/src/retranslation_pipeline.py` — dedicated pipeline, visible on Processing Page
- `backend/tests/test_retranslation_pipeline.py`
- `backend/tests/test_translator.py`
- `backend/tests/test_translation_tasks.py`
- `backend/tests/test_embedding_pipeline.py`
- `backend/tests/test_chat.py`
- `backend/tests/test_bootstrap.py`

### Backend (modified)
- `backend/src/ai/translator.py` — generalize direction logic, add Spanish
- `backend/src/tasks/translation_tasks.py` — add `translate_description_task_for_retranslation`
- `backend/src/main.py` — POST /api/translation/retranslate-all endpoint, bootstrap reader at startup

### Frontend (new)
- `frontend/src/i18n/index.ts`
- `frontend/src/i18n/locales/en.json`
- `frontend/src/i18n/locales/ru.json`
- `frontend/src/i18n/locales/es.json`
- `frontend/src/i18n/__tests__/completeness.test.ts`
- `frontend/src/pages/SetupWizard/StepLanguage.tsx`
- `frontend/build/installer.nsh`

### Frontend (modified)
- `frontend/package.json` — add react-i18next, i18next; add nsis.include, multiLanguageInstaller
- `frontend/src/main.tsx` or `App.tsx` — i18n init
- `frontend/src/pages/SetupWizard/index.tsx` — add StepLanguage as step 0
- `frontend/src/pages/SettingsPage.tsx` — add es, trigger re-translation, show progress
- All pages and components listed in Phase 8.6

## Open Questions / Future Phases
- **Pluralization**: Russian has complex plural rules. `react-i18next` supports ICU format
  (`{{count, plural, one {...} other {...}}`). Should be handled from the start in 8.6.
- **Right-to-left**: Not needed for EN/RU/ES but the i18n structure supports adding it.
- **Adding a 4th language**: Add to `LANG_DICT` in `translator.py` (if NLLB supports it),
  add locale JSON file, add to `SUPPORTED_LANGUAGES` array and NSIS `installerLanguages`.
  The completeness test (Phase 8.5) will catch any missing keys automatically.
- **Remote translation mode**: `translator.py` already supports `mode=remote`. For remote mode,
  query translation and description translation would call the remote AI instead of NLLB.
