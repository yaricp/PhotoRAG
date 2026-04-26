# Phase 5.7: Quantitative Auto-Tagging

**Goal:** Implement confidence-based tagging with a strictly gated threshold (> 0.5).

---

### Task 1: Schema Transformation (TDD)
- [ ] **Step 1: Convert `photo_tags` to `PhotoTag` Association Model** in `models.py`.
- [ ] **Step 2: Add `confidence_score` column**.
- [ ] **Step 3: [TDD] Write `test_tag_confidence.py`** to verify that a Photo can have a "Nature" tag with score 0.85.

### Task 2: Logic Refactoring (Renaming)
- [ ] **Step 1: Rename `ClipTagger.find_tags`**.
- [ ] **Step 2: Rename `auto_tag_clip_task`**.
- [ ] **Step 3: Update `db_service.add_photo_tag(photo_id, tag_name, score)`**.

### Task 3: Threshold Integration
- [ ] **Step 1: Implement the > 0.5 filter** in `auto_tag_clip_task`.
- [ ] **Step 2: Global Green Check**.
