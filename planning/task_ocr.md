# Task: Migrate OCR to EasyOCR (TDD)

## 1. Research & Planning
- [x] Research EasyOCR usage and multi-language support.
- [x] Create Implementation Plan.

## 2. Test-Driven Development (TDD) - Phase 1: Failing Tests
- [x] Create `backend/tests/test_ocr_engine.py` with tests for:
    - Singleton initialization.
    - Basic text extraction.
    - Multi-language support (RU + EN).
- [x] Run tests and verify they fail.

## 3. Infrastructure
- [x] Remove `pytesseract` from `backend/requirements.txt`.
- [x] Add `easyocr` to `backend/requirements.txt`.
- [x] Fix typo in `backend/requirements.txt`.
- [x] Run `pip install` to update environment.

## 4. Implementation
- [x] Update `backend/src/ai/ocr.py`:
    - Implement `EasyOCRReader` singleton.
    - Update `extract_text_from_image` function.
- [x] Update `backend/src/install.py`:
    - Add model download step.

## 5. Verification
- [x] Run `pytest backend/tests/test_ocr_engine.py`.
- [x] Run global test suite to ensure no regressions.
- [x] Create walkthrough.
