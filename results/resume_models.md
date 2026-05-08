# Project Status: Dynamic AI Model Configuration (Completed)

## Goal
To migrate AI model configurations from static environment variables (`.env` / `ML_Settings`) to a dynamic SQLite-backed configuration system, and provide a user interface to configure these models at runtime without requiring application restarts.

## Achieved Milestones
1. **Database Schema Setup**
   - Implemented `AIModelConfig` in `backend/src/models.py`.
   - Setup testing and confirmed models instantiate correctly.

2. **Backend API & Service Layer**
   - Created `AIModelConfigResponse` and `AIModelConfigUpdate` schemas in `schemas.py`.
   - Developed CRUD functions in `db_service.py` to get, update, and seed initial configs.
   - Built `GET /api/models/` and `PUT /api/models/{type}` endpoints in `main.py`.

3. **Registry Refactoring (Dynamic Caching)**
   - Updated the `AIModelRegistry` (`registry.py`) singleton to query `db_service` for configs when instantiating AI models.
   - Introduced `registry.reset_model(type)` to forcefully clear cached model instances in memory when a configuration is updated via the API, thus loading the updated settings dynamically on the next access.
   
4. **Setup Script Updates**
   - Enhanced `install.py` to call `init_default_model_configs` during setup to assure DB has fallback models (Qwen2-VL, ViT-B-32, nomic-embed, mBART, EasyOCR, gpt-4o-mini).

5. **Frontend Management Interface**
   - Implemented `frontend/src/pages/ModelsPage.tsx` using modern dynamic form structures to allow users to specify Execution Mode (`local`/`remote`), Model Identifier, and API credentials.
   - Added related API client fetching logic in `frontend/src/api/client.ts`.
   - Updated the Sidebar navigation to route users directly to the Models page.

## Testing
- Unit tests run using `pytest` for db_services, main routes, and registry logic (`backend/tests/test_db_service.py`, `backend/tests/test_main.py`, `backend/tests/test_registry.py`).
- Mocks utilized properly to avoid unneeded resource loads (e.g. mocking out huggingface transformers in isolated tests).

## Next Steps
- Implement frontend e2e testing (Playwright) if necessary to ensure `ModelsPage` interactions result in appropriate DB transitions.
- Validate that the AI Background pipeline seamlessly picks up changed models without latency spikes.
