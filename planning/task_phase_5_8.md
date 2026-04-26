# Phase 5.8: Hierarchical Auto-Categorization

**Goal:** Separate broad classification (Categories) from detailed labeling (Tags) with scored relationships.

---

### Task 1: Schema Evolution (TDD)
- [ ] **Step 1: Convert `photo_categories` to `PhotoCategory` Model** in `models.py`.
- [ ] **Step 2: Add `confidence_score` column**.
- [ ] **Step 3: [TDD] Write `test_category_scoring.py`** to verify scored classification storage.

### Task 2: Dynamic Vectorization
- [ ] **Step 1: Implement `ClipTagger.categorize`** (dynamic text encoding).
- [ ] **Step 2: Add `get_all_categories`** to `db_service.py`.
- [ ] **Step 3: Auto-seed defaults** (Landscape, Portrait, Urban, etc.) if empty.

### Task 3: Parallel Categorization Task
- [ ] **Step 1: Create `categorize_photo_task`** in `tasks.py`.
- [ ] **Step 2: Update Observer** to dispatch the new task.
- [ ] **Step 3: Global Green Check**.
