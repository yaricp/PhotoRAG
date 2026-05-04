# Implementation Plan: Replace Tesseract with EasyOCR

This plan outlines the steps to replace the legacy `pytesseract` engine with `EasyOCR`, providing better accuracy and native multi-language support.

## User Review Required

> [!IMPORTANT]
> **Disk Space**: EasyOCR will download approximately 100-300MB of model weights upon first initialization.
> **Dependencies**: `EasyOCR` depends on `torch` and `cv2`. Since `torch` is already in our requirements, the additional footprint is minimal.
> **Fix**: I will also fix the typo in `requirements.txt` where `sqlite-vec` and `langchain-openai` were merged.

## Proposed Changes

### 1. Dependencies

#### [MODIFY] [requirements.txt](file:///Users/yaricp/Projects/MyOwn/Photo_describer2/backend/requirements.txt)
- Remove `pytesseract`.
- Add `easyocr`.
- Fix line 26: `sqlite-vec` and `langchain-openai`.

---

### 2. OCR Core

#### [MODIFY] [ocr.py](file:///Users/yaricp/Projects/MyOwn/Photo_describer2/backend/src/ai/ocr.py)
- Implement a singleton `EasyOCRReader` class to manage the `easyocr.Reader` instance.
- Update `extract_text_from_image` to use the singleton.
- Support multiple languages (e.g., `['ru', 'en']`).

---

### 3. Installation & Setup

#### [MODIFY] [install.py](file:///Users/yaricp/Projects/MyOwn/Photo_describer2/backend/src/install.py)
- Add `install_ocr` function to pre-download models if OCR is in `local_models`.

---

### 4. Verification Plan

#### [NEW] [test_ocr.py](file:///Users/yaricp/Projects/MyOwn/Photo_describer2/backend/tests/test_ocr.py)
- Test that the reader initializes correctly.
- Test text extraction from a sample image (mocked or small test asset).
- Test that multi-language support is functional.

## TDD Workflow
1. Create `backend/tests/test_ocr.py` with failing tests.
2. Update `requirements.txt` and install dependencies.
3. Update `src/ai/ocr.py` to satisfy tests.
4. Verify all tests pass.
