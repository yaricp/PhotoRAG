# Implementation Plan: End-to-End Pipeline Testing

This plan describes the creation of a comprehensive End-to-End (E2E) test suite that validates the entire photo processing pipeline using real assets.

## User Review Required

> [!IMPORTANT]
> **Environment**: The E2E test will use the actual local models (EasyOCR, CLIP, etc.) if configured. This will be slow and memory-intensive.
> **Database**: A dedicated `test_e2e.sqlite3` will be used to avoid polluting production data.
> **Huey Configuration**: We will force Huey into `immediate` mode during the test so that tasks run sequentially in the main thread for verification.

## Proposed Changes

### 1. Test Infrastructure

#### [NEW] [test_e2e_pipeline.py](file:///Users/yaricp/Projects/MyOwn/Photo_describer2/backend/tests/test_e2e_pipeline.py)
- **Fixture `test_env`**: 
    - Setup a temporary "watched" folder.
    - Initialize a fresh SQLite database.
    - Patch `huey` to run tasks synchronously.
- **Test Case `test_full_pipeline_doc1`**:
    1. Copy `Pictures/doc1.png` to the watched folder.
    2. Manually invoke `PhotoEventHandler.on_created` (simulating the OS event).
    3. Assert that the database contains:
        - A photo record with the correct hash.
        - Technical metadata (ISO, resolution).
        - OCR text (extracted via EasyOCR).
        - Description (generated via Vision).
        - Tags (generated via CLIP).
        - `is_doc = True`.

---

### 2. Dependency Management

#### [MODIFY] [conftest.py](file:///Users/yaricp/Projects/MyOwn/Photo_describer2/backend/tests/conftest.py) (Optional)
- Add global fixtures for shared test resources if needed.

---

## Verification Plan

### Automated E2E Test
- Run `pytest backend/tests/test_e2e_pipeline.py -v -s`.
- Monitor logs to ensure the pipeline transitions through all phases:
    - `init` -> `first` (metadata, clip, vision)
    - `first` -> `second` (final embedding)
    - `second` -> `third` (ocr, doc detection)

### Manual Verification
- Dropping `doc1.png` into the actual watched folder while the server is running and checking the UI/Logs.
