# Phase 5.12: Warm-Worker Optimization

**Goal:** Implement a Singleton Registry to keep AI models resident in VRAM/RAM, eliminating per-photo loading latency and preventing memory fragmentation.

---

### Task 1: Singleton Model Registry
- [ ] **Step 1: Create `backend/src/ai/registry.py`**.
- [ ] **Step 2: Implement `AIModelRegistry`** with lazy-loading property getters for:
    - `ClipTagger`
    - `QwenVisionGenerator`
    - `SentenceTransformer` (Nomic)
- [ ] **Step 3: [TDD] Write `test_registry.py`** to verify that multiple calls return the same object instance.

### Task 2: Service Refactor
- [ ] **Step 1: Update `tasks.py`** to use the Registry instead of local instantiation.
- [ ] **Step 2: Update `download_models_task`** to use the Registry for pre-warming models.

### Task 3: Performance Verification
- [ ] **Step 1: Measure Processing Speed** of Photo 1 vs Photo 2.
- [ ] **Step 2: Global Green Check** (all 48+ tests passing with Warm Registry).
