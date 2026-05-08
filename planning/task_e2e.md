# Task: End-to-End Pipeline Verification

## 1. Preparation
- [x] Verify `Pictures/doc1.png` is accessible.
- [x] Create `backend/tests/test_e2e_pipeline.py` skeleton.

## 2. Infrastructure Setup
- [x] Setup `pytest` fixture for temporary watched directory.
- [x] Setup `pytest` fixture for isolated SQLite DB.
- [x] Implement Huey `immediate` mode patch.

## 3. Test Implementation
- [x] Implement `test_full_pipeline_doc1`:
    - [x] Simulate file creation.
    - [x] Wait for all phases to complete.
    - [x] Assert metadata extraction.
    - [x] Assert CLIP tagging.
    - [x] Assert Vision description.
    - [x] Assert EasyOCR text extraction.
    - [x] Assert Document classification.

## 4. Execution & Debugging
- [x] Run E2E test.
- [x] Fix any pipeline synchronization issues discovered.
- [x] Finalize walkthrough.
