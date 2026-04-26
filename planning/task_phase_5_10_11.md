# Phase 5.10 & 5.11: Semantic Synthesis & Nomic Alignment

**Goal:** Vectorize photos using the high-fidelity Nomic embedder and synthesize AI outputs into narratives.

---

### Task 1: Racing Finalizer Pattern
- [x] **Step 1: Implement `check_and_trigger_finalization`** barrier.
- [x] **Step 2: Update all AI tasks** to signal completion to the barrier.
- [x] **Step 3: Implement `final_embedding_task`** to weave Scene + Tags + Category + Geo.

### Task 2: Nomic-AI Integration
- [x] **Step 1: Switch to `nomic-ai/nomic-embed-text-v1.5`** (768-dim).
- [x] **Step 2: Implement Bootstrap check** in `download_models_task`.
- [x] **Step 3: Fix Import Conflicts** via Lazy-Loading (resolving `transformers` shadowing).

### Task 3: Global Green Check
- [x] Verified **48 passed tests** (Full Semantic Pipeline Stability).
