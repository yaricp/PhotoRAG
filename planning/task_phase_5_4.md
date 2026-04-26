# Phase 5.4: System Bootstrap & Model Orchestration

**Goal:** Create a robust startup sequence that handles model downloading and reports status to the UI.

---

### Task 1: Model Status Tracking (DB)
**Files:**
- Modify: `backend/src/models.py`
- Modify: `backend/src/db_service.py`

- [ ] **Step 1: Add `ModelState` table** (id, name, status, progress, updated_at)
- [ ] **Step 2: Add `update_model_status` helper in `db_service.py`**
- [ ] **Step 3: [TDD] Verify we can query model status**

### Task 2: Bootstrap Background Tasks
**Files:**
- Modify: `backend/src/tasks.py`
- Modify: `backend/src/ai/clip.py`, `backend/src/ai/vision.py`

- [ ] **Step 1: Implement `download_models_task`**
- [ ] **Step 2: Wrap HF/OpenCLIP loaders to report download start/finish to DB**

### Task 3: The Python Orchestrator (`run.py`)
**Files:**
- [NEW] `backend/run.py`

- [ ] **Step 1: Implement process manager** (Start Worker -> Start API)
- [ ] **Step 2: Check for missing models on startup and fire bootstrap tasks**

### Task 4: API Endpoint for Status
**Files:**
- Modify: `backend/src/main.py`

- [ ] **Step 1: Add `/api/system/status` endpoint for Frontend polling**
