# Dynamic AI Models Configuration

## Goal Description
Currently, AI models (Vision, CLIP, Embedding, Translator, Chat, OCR) and their modes (local/remote, URLs, API keys) are configured statically via `.env` variables using Pydantic Settings in `src/config.py`. The goal is to move this configuration into the SQLite database, provide REST API endpoints to manage these settings dynamically, and build a UI page in the React frontend to configure them without touching code.

## Proposed Changes

### 1. Database Schema (`backend/src/models.py`)
Add a new model `AIModelConfig` to store the configuration.

#### [NEW] `AIModelConfig`
```python
class AIModelConfig(Base):
    __tablename__ = "ai_model_configs"
    id = Column(Integer, primary_key=True, index=True)
    type = Column(String, unique=True, index=True) # e.g. 'vision', 'clip', 'embedding', 'translator', 'chat', 'ocr'
    mode = Column(String, default="local") # "local" or "remote"
    model_name = Column(String) # e.g. "Qwen/Qwen2-VL-2B-Instruct"
    url = Column(String, nullable=True)
    api_key = Column(String, nullable=True)
```

### 2. Schemas & DB Services
#### [MODIFY] `backend/src/schemas.py`
- Add `AIModelConfigResponse`, `AIModelConfigUpdate` pydantic schemas.

#### [MODIFY] `backend/src/db_service.py`
- Add CRUD operations:
  - `get_all_model_configs(db)`
  - `get_model_config(db, type)`
  - `update_model_config(db, type, schema)`
  - `init_default_model_configs(db)` (to insert defaults if empty)

### 3. API Endpoints (`backend/src/main.py`)
- **GET `/api/models/`**: Returns list of all `AIModelConfigResponse`.
- **PUT `/api/models/{type}`**: Updates the config for a given type and re-initializes the model in the registry if needed.

### 4. Registry Refactoring (`backend/src/ai/registry.py`)
Currently, `AIModelRegistry` reads from `self.settings` (which uses `ML_Settings`).
- **Change**: Replace references to `self.settings.VISION_MODE`, etc., with a dynamic DB lookup.
- We will add a helper method in `registry` that opens a short-lived `SessionLocal()` to read the `AIModelConfig` for the requested model type before instantiating it.
- **Cache Invalidation**: When a config is updated via the API, the API must tell the registry to clear the cached instance of that model (`self._vision_generator = None`) so it reloads with the new settings on the next call.

### 5. Installation Script (`backend/src/install.py`)
- Update the initialization script to populate the `ai_model_configs` table with default values (taken from the old `ML_Settings`) during the setup phase, so that the database is pre-seeded before the server starts.

### 6. Frontend Implementation
#### [MODIFY] `frontend/src/types/api.ts` & `client.ts`
- Add Typescript interfaces matching `AIModelConfigResponse`.
- Add API client methods for `GET` and `PUT` models.

#### [NEW] `frontend/src/pages/ModelsPage.tsx`
- A new UI route (already added to Sidebar by user) that displays a list of all model types.
- For each model, a card allowing the user to select `Local` or `Remote`.
- If `Local`, an input for the `model_name` (huggingface repo or local path).
- If `Remote`, inputs for `URL`, `API Key`, and `Model Name`.
- "Save" button to trigger the PUT request.

## Verification Plan

### Automated Tests (TDD)
- **Backend Tests**: 
  - Add tests in `test_db_service.py` for creating and updating model configs.
  - Add tests in `test_main.py` to verify `/api/models/` endpoints.
  - Add tests in `test_registry.py` to mock DB and verify it loads the model according to the DB configuration, and resets when updated.
- **Frontend Tests**: 
  - Unit tests for the new API client endpoints using MSW.
  - Component tests for `ModelsPage.tsx` verifying form logic (showing/hiding URL/API keys based on mode).

## User Review Required
> [!IMPORTANT]
> The Registry is a singleton, meaning if a user changes a model configuration via the UI while the backend is running, we must unload the old model from RAM to load the new one. I will add a `.reset_model(model_type)` function to the Registry that sets `_vision_generator = None` (and deletes it from memory), which will be called automatically by the `PUT /api/models/` endpoint. Are you okay with this approach?
