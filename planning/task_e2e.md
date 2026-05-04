# Task: End-to-End Pipeline Verification

## 1. Preparation
- [ ] Verify `Pictures/doc1.png` is accessible.
- [ ] Create `backend/tests/test_e2e_pipeline.py` skeleton.

## 2. Infrastructure Setup
- [ ] Setup `pytest` fixture for temporary watched directory.
- [ ] Setup `pytest` fixture for isolated SQLite DB.
- [ ] Implement Huey `immediate` mode patch.

## 3. Test Implementation
- [ ] Implement `test_full_pipeline_doc1`:
    - Simulate file creation.
    - Wait for all phases to complete.
    - Assert metadata extraction.
    - Assert CLIP tagging.
    - Assert Vision description.
    - Assert EasyOCR text extraction.
    - Assert Document classification.

## 4. Execution & Debugging
- [ ] Run E2E test.
- [ ] Fix any pipeline synchronization issues discovered.
- [ ] Finalize walkthrough.
