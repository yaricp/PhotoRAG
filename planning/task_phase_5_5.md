# Phase 5.5: Semantic Relational Expansion

**Goal:** Transform the flat Photo model into a normalized, searchable semantic network.

---

### Task 1: Relational Schema (TDD)
- [ ] **Step 1: Define Association Tables** in `models.py` for Tag, Person, Keyword, Category.
- [ ] **Step 2: Define Entity Classes** (Tag, Person, Keyword, Category, Camera, Geoposition).
- [ ] **Step 3: Update `Photo` class** with relationships and foreign keys.
- [ ] **Step 4: [TDD] Write `test_models_relational.py`** to verify that adding a Keyword to a Photo persists correctly in the association table.

### Task 2: Refactoring Tasks for Relational Data
- [ ] **Step 1: Update `metadata_task`** to create/link `Camera` and `Geoposition` objects.
- [ ] **Step 2: Update `clip_task`** to populate the `Keyword` model.
- [ ] **Step 3: Verify with Integrated Tests**

### Task 3: Database Migration/Init
- [ ] **Step 1: Update `run.py`** to handle the new schema creation.
