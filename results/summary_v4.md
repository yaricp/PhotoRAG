# Photo Describer 2 — Project Summary v4

> Generated: 2026-05-05 | Commit: `04242ed`  
> Last milestone: **EasyOCR migration + pipeline restructure + E2E tests**

---

## Project Overview

**Photo Describer 2** is an AI-powered photo management backend that automatically processes photos through a multi-phase pipeline: extracting metadata, generating visual descriptions, running OCR on documents, classifying images with CLIP, embedding everything into a vector database for semantic search, and translating content between languages.

**Stack:** Python 3.13, FastAPI, SQLite + sqlite-vec, Huey (SqliteHuey), SQLAlchemy, EasyOCR, CLIP (open-clip-torch), Qwen VL (vision), Nomic Embed (embeddings), NLLB (translation), LangGraph (AI agent), Watchdog (filesystem observer).

---

## Directory Structure

```
Photo_describer2/
├── backend/                   # Main backend package (Python 3.13, uv)
│   ├── run.py                 # Worker process launcher
│   ├── pyproject.toml         # Project config & dependencies
│   ├── requirements.txt       # Pinned requirements
│   ├── uv.lock                # uv lockfile
│   └── src/
│       ├── main.py            # FastAPI application
│       ├── config.py          # Pydantic Settings (Main_Settings, ML_Settings, Api_Settings)
│       ├── models.py          # SQLAlchemy ORM models
│       ├── schemas.py         # Pydantic schemas (request/response)
│       ├── database.py        # Engine, SessionLocal, sqlite-vec loader
│       ├── deps.py            # FastAPI dependency injectors (get_db, get_translator)
│       ├── db_service.py      # All DB CRUD operations
│       ├── vector_db_services.py  # sqlite-vec embedding save/search
│       ├── observer.py        # Watchdog filesystem event handler
│       ├── watcher_service.py # Watcher lifecycle management
│       ├── geo.py             # Geolocation reverse-geocoding (geopy)
│       ├── utils.py           # File hashing, EXIF extraction, helpers
│       ├── metadata.py        # EXIF metadata parsing
│       ├── install.py         # Model pre-download / installation script
│       ├── ai/
│       │   ├── registry.py    # AIModelRegistry singleton (lazy-loads all models)
│       │   ├── clip.py        # ClipTagger: find_tags(), categorize()
│       │   ├── vision.py      # VisionGenerator: Qwen VL image→text
│       │   ├── ocr.py         # EasyOCRReader singleton + extract_text_from_image()
│       │   ├── translator.py  # Translator (NLLB): translate()
│       │   └── prompts.py     # Prompt templates + build_photo_text_for_embedding()
│       ├── queues/
│       │   ├── clip_queue.py       # SqliteHuey queue "clip" (warms CLIP on startup)
│       │   ├── vision_queue.py     # SqliteHuey queue "vision" (warms Qwen VL)
│       │   ├── embedding_queue.py  # SqliteHuey queue "embedding" (warms Nomic + translator)
│       │   └── translation_queue.py # SqliteHuey queue "translate" (warms translator)
│       ├── tasks/
│       │   ├── __init__.py         # start_pipeline() entry point
│       │   ├── utils.py            # phase_logic(), _dispatch_tasks(), _finish_task(), _start_next_phase()
│       │   ├── clip_tasks.py       # metadata_task, auto_tag_clip_task, categorize_photo_task
│       │   ├── vision_tasks.py     # vision_task, is_this_document_task, ocr_task
│       │   ├── embedding_tasks.py  # final_embedding_task, embedding_document_text_task
│       │   └── translation_tasks.py # translate_description_task
│       └── graphs/
│           ├── ai_agent.py    # LangGraph conversational AI agent
│           ├── ingestion.py   # LangGraph ingestion graph
│           ├── tools.py       # Agent tools (search photos, get tags, etc.)
│           └── state.py       # Graph state definitions
├── backend/tests/
│   ├── conftest.py                    # Shared fixtures
│   ├── test_e2e_pipeline.py           # ★ E2E: Observer → DB full pipeline (145 lines)
│   ├── test_ocr_engine.py             # ★ OCR: EasyOCR singleton unit tests (50 lines)
│   ├── test_geo.py                    # Geolocation mocking tests (44 lines)
│   ├── test_main.py                   # FastAPI endpoint tests (129 lines)
│   ├── test_models.py                 # ORM model tests (34 lines)
│   ├── test_models_relational.py      # Relational model tests (76 lines)
│   ├── test_observer.py               # Watchdog observer tests (45 lines)
│   ├── test_db_service.py             # DB service unit tests (92 lines)
│   ├── test_tasks_parallel.py         # Parallel task orchestration tests (76 lines)
│   ├── test_registry.py               # AIModelRegistry tests (43 lines)
│   ├── test_registry_llm.py           # LLM registry tests (54 lines)
│   ├── test_bootstrap.py              # Bootstrap / install tests (51 lines)
│   ├── test_synthesis.py              # Synthesis tests (40 lines)
│   ├── test_agent_tools.py            # Agent tool tests (60 lines)
│   ├── test_ai_agent.py               # AI agent tests (78 lines)
│   ├── test_api_chat.py               # Chat API tests (60 lines)
│   ├── test_doc_intelligence.py       # Document intelligence tests (56 lines)
│   ├── test_category_scoring.py       # Category scoring tests (84 lines)
│   ├── test_clip_vocabulary.py        # CLIP vocabulary tests (59 lines)
│   ├── test_tag_confidence.py         # Tag confidence tests (62 lines)
│   ├── test_database.py               # Database setup tests (6 lines)
│   ├── test_config.py                 # Config tests (7 lines)
│   ├── ai/
│   │   ├── test_clip.py               # CLIP model tests (62 lines)
│   │   ├── test_ocr.py                # OCR legacy tests (6 lines)
│   │   ├── test_prompts.py            # Prompt tests (4 lines)
│   │   ├── test_vision.py             # Vision model tests (38 lines)
│   │   └── test_vision_logic.py       # Vision logic tests (36 lines)
│   └── graphs/
│       └── test_ingestion_graph.py    # Graph ingestion tests (4 lines)
├── planning/                          # Implementation plans & task trackers
│   ├── implementation_plan.md
│   ├── implementation_plan_e2e.md     # ★ E2E test plan (current)
│   ├── implementation_plan_ocr.md     # ★ EasyOCR migration plan
│   ├── task.md
│   ├── task_chatbot.md
│   ├── task_e2e.md                    # ★ E2E task tracker
│   ├── task_ocr.md                    # ★ OCR task tracker
│   ├── task_phase7.md … task_phase_5_13.md  # Historical phase plans
│   └── walkthrough_ocr.md             # ★ OCR migration walkthrough
├── results/
│   ├── summary.md             # v1 summary
│   ├── summary_v2.md          # v2 summary
│   ├── summary_v3.md          # v3 summary
│   └── summary_v4.md          # ← this file
├── data/                      # Data directory (gitignored binaries)
├── .gitignore
└── venv/                      # Legacy Python 3.9 venv (superseded by backend/.venv)
```

---

## Processing Pipeline (3 Phases)

```mermaid
graph TD
    FS[Filesystem Event] --> OBS[PhotoEventHandler.on_created]
    OBS --> DB1[Create Photo in DB]
    DB1 --> PIPE[start_pipeline()]

    PIPE --> FIRST[Phase: first]
    FIRST --> MT[metadata_task]
    FIRST --> CT[auto_tag_clip_task]
    FIRST --> CP[categorize_photo_task]
    FIRST --> VT[vision_task]
    FIRST --> OCR[ocr_task]

    MT & CT & CP & VT & OCR --> SECOND[Phase: second]
    SECOND --> FE[final_embedding_task]
    SECOND --> TD[translate_description_task]
    SECOND --> ID[is_this_document_task]

    FE & TD & ID --> THIRD[Phase: third]
    THIRD --> EDT[embedding_document_text_task]

    EDT --> DONE[✅ Complete]
```

| Phase | Queue | Tasks |
|---|---|---|
| **first** | clip + vision | `metadata_task`, `auto_tag_clip_task`, `categorize_photo_task`, `vision_task`, `ocr_task` |
| **second** | embedding + translate + vision | `final_embedding_task`, `translate_description_task`, `is_this_document_task` |
| **third** | embedding | `embedding_document_text_task` (docs only) |

---

## AI Models & Registry

All models are managed by the **`AIModelRegistry` singleton** (`src/ai/registry.py`, 219 lines). Models are lazy-loaded on first access via `@property`.

| Property | Model | Purpose |
|---|---|---|
| `clip_tagger` | OpenCLIP (ViT-B-32) | Tags & categories |
| `vision_generator` | Qwen2.5-VL-3B-Instruct | Scene description, document detection |
| `nomic_embedder` | nomic-embed-text-v1.5 | 768-dim text embeddings |
| `translator` | Facebook NLLB-200 | RU↔EN translation |
| `ocr` | EasyOCR (ru+en) | Text extraction from images |

**Warm-up:** Each worker queue calls `on_startup()` to pre-load its required model(s) before accepting tasks.

---

## OCR Engine (EasyOCR) — Migrated in v4

`src/ai/ocr.py` — **47 lines**

```python
class EasyOCRReader:
    _instance = None
    _languages = None

    @classmethod
    def get_instance(cls, languages=None) -> easyocr.Reader:
        # Singleton: recreates only if language list changes
        ...

def extract_text_from_image(filepath: str, lang: str = None) -> str:
    # Defaults to ['ru', 'en']
    ...
```

**Key changes from pytesseract:**
- Language-change detection — singleton recreated only when needed
- Proper `FileNotFoundError` handling
- Language list as Python list (not `"rus+eng"` string)

---

## API Endpoints

**FastAPI app** (`src/main.py`, 207 lines) — all endpoints tagged for Swagger grouping.

| Method | Path | Tag | Description |
|---|---|---|---|
| `GET` | `/api/system/status/` | System | Model states |
| `POST` | `/api/watch/` | Watchers | Start directory watcher |
| `GET` | `/api/watchers/` | Watchers | List active watchers |
| `GET` | `/api/stream/` | — | SSE placeholder |
| `GET` | `/api/photos/{photo_id}` | Photos | Get single photo |
| `GET` | `/api/photos/` | Photos | Paginated photo list (filter/sort) |
| `DELETE` | `/api/photos/{photo_id}` | Photos | Delete photo + cascade |
| `POST` | `/api/search/` | Photos | Semantic vector search |
| `GET` | `/api/tags/` | — | All tags |
| `GET` | `/api/categories/` | — | All categories |
| `GET` | `/api/cameras/` | — | All cameras |
| `GET` | `/api/geopositions/` | — | All geopositions |
| `POST` | `/api/chat/` | Agent | Chat with AI agent |
| `GET` | `/api/job/{photo_id}` | Jobs | Get processing job status |

---

## Database Models (`src/models.py`, 161 lines)

| Model | Key Fields |
|---|---|
| `Photo` | `file_path`, `hash`, `description`, `translated_description`, `ocr_text`, `is_doc`, `captured_at` |
| `Tag` / `PhotoTag` | `name`, `score` |
| `Category` / `PhotoCategory` | `name`, `prompt`, `score` |
| `Camera` | `make`, `model`, `lens` |
| `Geoposition` | `lat`, `lon`, `address`, `display_name` |
| `ModelState` | `name`, `status` |
| `Watcher` | `path`, `status` |
| `ProcessingJob` | `photo_id`, `phase`, `tasks` (comma-separated task names) |
| `PhotoEmbedding` | `photo_id`, `model`, `created_at` |

---

## Worker Processes (`run.py`, 60 lines)

```python
QUEUE_MAP = {
    "clip":      "src.queues.clip_queue.clip_queue",
    "vision":    "src.queues.vision_queue.vision_queue",
    "embedding": "src.queues.embedding_queue.embedding_queue",
    "translate": "src.queues.translation_queue.translate_queue",
}
```

Workers are started by `run.py` based on `ML_Settings.local_models` list. Each queue uses `SqliteHuey` with a dedicated `.sqlite3` file.

---

## Test Suite Summary

**Total test files:** 29 | **Total test lines:** ~1,517

| Category | Files | Lines | Notes |
|---|---|---|---|
| **E2E Pipeline** | `test_e2e_pipeline.py` | 145 | Full Observer→DB pipeline with real `doc1.png` |
| **OCR Engine** | `test_ocr_engine.py` | 50 | Singleton lifecycle, language switching |
| **API** | `test_main.py` | 129 | All FastAPI endpoints |
| **Tasks** | `test_tasks_parallel.py` | 76 | Phase orchestration, parallel dispatch |
| **AI Agent** | `test_ai_agent.py` | 78 | LangGraph agent chat |
| **Category/Tag** | `test_category_scoring.py` + `test_tag_confidence.py` + `test_clip_vocabulary.py` | 205 | CLIP classification |
| **DB Service** | `test_db_service.py` | 92 | CRUD operations |
| **Models** | `test_models.py` + `test_models_relational.py` | 110 | ORM + relationships |
| **Geolocation** | `test_geo.py` | 44 | Reverse geocoding mock |
| **Registry** | `test_registry.py` + `test_registry_llm.py` | 97 | Singleton + LLM models |
| **Observer** | `test_observer.py` | 45 | Filesystem events |
| **Other** | Various | ~449 | Chat API, tools, synthesis, ingestion graph… |

### E2E Test Strategy (`test_e2e_pipeline.py`)

```python
@pytest.fixture(autouse=True)
def mock_ai_registry():
    # Patch AIModelRegistry CLASS properties to prevent
    # model loading during tests
    mock_tagger = MagicMock()      # clip_tagger
    mock_embedder = MagicMock()    # nomic_embedder (name via PropertyMock)
    
    with patch.object(AIModelRegistry, 'clip_tagger', ...),
         patch.object(AIModelRegistry, 'nomic_embedder', ...),
         patch.object(AIModelRegistry, 'generate_vision_text', ...),
         patch.object(AIModelRegistry, 'embedder_encode_text', ...):
        with patch('src.tasks.vision_tasks.extract_text_from_image') as mock_ocr:
            yield ...

def test_full_pipeline_e2e(test_db, watch_dir):
    # 1. Copy real doc1.png to tmp watch_dir
    # 2. Fire PhotoEventHandler.on_created()
    # 3. All queues run in .immediate=True mode (synchronous)
    # 4. Assert: photo.description, photo.is_doc, photo.ocr_text, tags, categories
```

---

## Configuration (`src/config.py`, 95 lines)

```python
class ML_Settings(BaseSettings):
    CLIP_MODE: str = "local"          # local | remote
    VISION_MODE: str = "local"
    EMBEDDING_MODE: str = "local"
    TRANSLATOR_MODE: str = "local"
    OCR_MODE: str = "local"
    CHAT_MODEL_MODE: str = "local"
    
    @property
    def local_models(self) -> list[str]:
        # Returns ["clip", "vision", "embedding", "translate"]
        # used by run.py to determine which workers to start

class Api_Settings(BaseSettings):
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEFAULT_LANGUAGE: str = "ru"

class Main_Settings(BaseSettings):
    WATCH_DIRECTORY: str
    DB_URL: str = "sqlite:///./photos.sqlite3"
    DEFAULT_LANGUAGE: str = "ru"
    IMAGE_RESIZE: int = 1024
```

---

## Key Source Files by Size

| File | Lines | Role |
|---|---|---|
| `src/install.py` | 381 | Model pre-download + DB migrations |
| `src/db_service.py` | 310 | All database CRUD operations |
| `src/ai/registry.py` | 219 | AI model singleton management |
| `src/main.py` | 207 | FastAPI app + all endpoints |
| `src/ai/clip.py` | 273 | CLIP tagging + categorization |
| `src/tasks/utils.py` | 160 | Pipeline phase orchestration |
| `src/tasks/clip_tasks.py` | 150 | Metadata + CLIP Huey tasks |
| `src/models.py` | 161 | All SQLAlchemy ORM models |
| `src/schemas.py` | 127 | All Pydantic request/response schemas |
| `src/vector_db_services.py` | 133 | sqlite-vec embedding operations |
| `src/tasks/embedding_tasks.py` | 123 | Embedding Huey tasks |
| `src/tasks/vision_tasks.py` | 120 | Vision + OCR Huey tasks |
| `src/ai/vision.py` | 104 | Qwen VL inference |
| `src/geo.py` | 102 | Geolocation reverse lookup |
| `src/ai/translator.py` | 90 | NLLB translation |

**Total backend source:** ~3,618 lines across 30 source files + 1,517 lines across 29 test files = **~5,135 lines**

---

## Git History (Last 10 Commits)

| Hash | Message |
|---|---|
| `04242ed` | feat: migrate OCR to EasyOCR, restructure pipeline phases, and add E2E tests |
| `f0b76e9` | refactor: reorganize task pipeline and enhance photo metadata processing |
| `f843327` | feat: implement agentic conversational photo assistant |
| `e0158c5` | added chat bot using LangChain and LangGraph |
| `61db63e` | added translator with preinstalled translation model |
| `9ddeaed` | added full_installation script. refactored tasks to three processes and three queues |
| `cd82223` | made searching by vectors more accurate |
| `b23a6e2` | added endpoints for filtering and sorting photos |
| `9c680a5` | added sqlite-vec for sqlite3 + embedding for vector DB |
| `0c8d6ca` | added resize property, OCR recognition, phase-based task orchestration |

---

## Known Open Issues (as of v4)

1. **E2E test `is_doc` assertion fails** — `is_this_document_task` is now in phase **second**, but the mock for `generate_vision_text` triggers for `describe_scene` (pk from vision_task), not `is_document`. The E2E test needs its assertions aligned with the new 3-phase structure (check after phase second completes).

2. **`nomic_embedder.name` is NoneType** in embedding task — `patch.object(AIModelRegistry, 'nomic_embedder', ...)` on the class vs. instance causes the getter to still fire during setup. Needs further investigation: possibly use `patch.object(registry_instance, ...)` after `immediate=True` is confirmed working.

3. **`embedding_document_text_task`** relies on `registry.translator` — needs to be included in the E2E test mock fixture.

4. **`translate` missing from `run.py` worker map** for older workers (now fixed in latest commit).

---

## Next Steps

- [ ] Fix E2E test assertions to match new 3-phase pipeline
- [ ] Properly mock `nomic_embedder`, `translator`, and `is_this_document_task` in E2E fixture
- [ ] Add `embedding_document_text_task` to E2E test coverage
- [ ] Run full test suite and address remaining failures
- [ ] Frontend integration (Vue/React UI consuming FastAPI)
- [ ] Add `test_translation_tasks.py` for translate pipeline phase
