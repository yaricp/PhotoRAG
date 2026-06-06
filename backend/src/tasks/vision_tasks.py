"""Phase-1, phase-2, and phase-3 vision and OCR tasks — called by incoming_pipeline.py."""

import asyncio

from loguru import logger

from src.db.database import SessionLocal
from src.db_service import get_photo_by_id
from src.model_services import call_ocr_model, call_vision_model
from src.pipeline_tracker import track_task

# ---------------------------------------------------------------------------
# Sync DB helpers — run via asyncio.to_thread to avoid blocking the event loop
# ---------------------------------------------------------------------------


def _get_vision_input_sync(photo_id: int) -> str | None:
    """Return file_path, or None if photo not found."""
    db = SessionLocal()
    try:
        photo = get_photo_by_id(db, photo_id)
        return photo.file_path if photo else None
    finally:
        db.close()


def _get_doc_input_sync(photo_id: int) -> tuple[str | None, bool]:
    """Return (file_path, is_doc) for ocr_task pre-check."""
    db = SessionLocal()
    try:
        photo = get_photo_by_id(db, photo_id)
        if not photo:
            return None, False
        return photo.file_path, bool(photo.is_doc)
    finally:
        db.close()


def _save_description_sync(photo_id: int, desc: str) -> None:
    db = SessionLocal()
    try:
        photo = get_photo_by_id(db, photo_id)
        if photo:
            photo.description = desc
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _save_is_doc_sync(photo_id: int, is_doc: bool) -> None:
    db = SessionLocal()
    try:
        photo = get_photo_by_id(db, photo_id)
        if photo:
            photo.is_doc = is_doc
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _save_ocr_text_sync(photo_id: int, text: str) -> None:
    db = SessionLocal()
    try:
        photo = get_photo_by_id(db, photo_id)
        if photo and text and text.strip():
            photo.ocr_text = text
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Async task functions
# ---------------------------------------------------------------------------


async def vision_task(photo_id: int) -> None:
    """Generate a natural-language description of the photo."""
    logger.info(f"[vision] Start: photo_id={photo_id}")
    async with track_task(photo_id, "phase_1", "vision_task"):
        file_path = await asyncio.to_thread(_get_vision_input_sync, photo_id)
        if not file_path:
            return
        desc = await call_vision_model(file_path=file_path, prompt_key="describe_scene")
        await asyncio.to_thread(_save_description_sync, photo_id, desc)
        logger.info(f"[vision] Photo {photo_id}: description saved ✓")


async def is_this_document_task(photo_id: int) -> None:
    """Classify whether the photo is a document (yes/no)."""
    logger.info(f"[vision/doc] Start: photo_id={photo_id}")
    async with track_task(photo_id, "phase_2", "is_this_document_task"):
        file_path = await asyncio.to_thread(_get_vision_input_sync, photo_id)
        if not file_path:
            return
        result = await call_vision_model(file_path=file_path, prompt_key="is_document")
        is_doc = "yes" in result.lower()
        await asyncio.to_thread(_save_is_doc_sync, photo_id, is_doc)
        logger.info(f"[vision/doc] Photo {photo_id}: is_doc={is_doc} ✓")


async def ocr_task(photo_id: int) -> None:
    """Extract text from the photo via OCR (skips non-documents)."""
    logger.info(f"[ocr] Start: photo_id={photo_id}")
    async with track_task(photo_id, "phase_3", "ocr_task"):
        file_path, is_doc = await asyncio.to_thread(_get_doc_input_sync, photo_id)
        if not file_path:
            return
        if not is_doc:
            logger.info(f"[ocr] Photo {photo_id} is not a document, skipping OCR")
            return
        text = await call_ocr_model(file_path=file_path)
        await asyncio.to_thread(_save_ocr_text_sync, photo_id, text)
        logger.info(f"[ocr] Photo {photo_id}: text extracted ✓")
