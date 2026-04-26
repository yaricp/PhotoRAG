# Phase 5.6: CLIP Vocabulary Optimization

**Goal:** Implement pre-cached zero-shot classification using Open Images Dataset tags.

---

### Task 1: Vocabulary Generation (TDD)
- [ ] **Step 1: Implement CSV Parsing** in `ClipTagger.download()`.
- [ ] **Step 2: Implement Embedding Generation** in `ClipTagger.compute_embeddings()`.
- [ ] **Step 3: Save to `tags_features.npy`**.
- [ ] **Step 4: [TDD] Write `test_clip_vocabulary.py`** to verify CSV parsing and NumPy storage.

### Task 2: Vector Search Inference
- [ ] **Step 1: Implement `generate_keywords`** using Cosine Similarity against the loaded `.npy`.
- [ ] **Step 2: [TDD] Verify inference logic** with mocked model outputs.

### Task 3: Ingestion Pipeline Sync
- [ ] **Step 1: Update `download_models_task`** in `tasks.py` to call vocabulary prep.
- [ ] **Step 2: Global Green Check**.
