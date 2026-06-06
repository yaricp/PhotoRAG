"""Phase-2 and phase-4 embedding tasks — called by incoming_pipeline.py."""

import asyncio

from loguru import logger

from src.ai.prompts import build_photo_text_for_embedding
from src.config import Database_Settings as _DB_Settings
from src.config import Embedding_Settings, Main_Settings
from src.db.database import SessionLocal
from src.db_service import get_photo_by_id, get_setting
from src.model_services import call_embedding_model, call_translation_model
from src.pipeline_tracker import track_task
from src.vector_db_services import store_photo_embedding

_DB_PATH = _DB_Settings().DATABASE_PATH


# ---------------------------------------------------------------------------
# Sync DB helpers — run via asyncio.to_thread to avoid blocking the event loop
# ---------------------------------------------------------------------------


def _read_embedding_input_sync(photo_id: int) -> dict | None:
    """Read all fields needed to build the embedding text. Returns None if not found."""
    db = SessionLocal()
    try:
        photo = get_photo_by_id(db, photo_id)
        if not photo:
            return None
        tags = [pt.tag.name for pt in photo.tags_rel]
        categories = [pc.category.name for pc in photo.categories_rel]
        location = photo.geoposition.address if photo.geoposition and photo.geoposition.address else "Unknown Location"
        return {
            "description": photo.description,
            "tags": tags,
            "categories": categories,
            "location": location,
        }
    finally:
        db.close()


def _save_embedding_sync(photo_id: int, embedding: list[float]) -> None:
    from src.queues.queue_config import read_model_config_from_db

    db = SessionLocal()
    try:
        cfg = read_model_config_from_db(_DB_PATH, "embedding")
        model_name = (cfg and cfg.get("model_name")) or Embedding_Settings().PHOTO_EMBEDDER_MODEL
        store_photo_embedding(db, photo_id, embedding, model_name)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _read_doc_input_sync(photo_id: int) -> tuple[bool, str | None]:
    """Return (is_doc, ocr_text). Returns (False, None) if photo not found."""
    db = SessionLocal()
    try:
        photo = get_photo_by_id(db, photo_id)
        if not photo:
            return False, None
        return bool(photo.is_doc), photo.ocr_text
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Async task functions
# ---------------------------------------------------------------------------


async def final_embedding_task(photo_id: int) -> None:
    """
    Aggregate phase-1 results (description, tags, categories, location)
    into a normalised embedding vector and store it for semantic search.
    """
    logger.info(f"[embedding] Start: photo_id={photo_id}")
    async with track_task(photo_id, "phase_2", "final_embedding_task"):
        inputs = await asyncio.to_thread(_read_embedding_input_sync, photo_id)
        if inputs is None:
            return

        photo_text = build_photo_text_for_embedding(
            description=inputs["description"],
            tags=inputs["tags"],
            categories=inputs["categories"],
            location=inputs["location"],
        )
        logger.debug(f"[embedding] Photo {photo_id}: built text for embedding: {photo_text}")
        embedding = await call_embedding_model(text=photo_text, purpose="save")
        await asyncio.to_thread(_save_embedding_sync, photo_id, embedding)
        logger.info(f"[embedding] Photo {photo_id}: vector saved ✓")


async def embedding_document_text_task(photo_id: int) -> None:
    """
    For documents: translate the OCR text to English and embed it
    as a second search vector.
    """
    logger.info(f"[embedding/doc] Start: photo_id={photo_id}")
    async with track_task(photo_id, "phase_4", "embedding_document_text_task"):
        is_doc, ocr_text = await asyncio.to_thread(_read_doc_input_sync, photo_id)
        if not is_doc or not ocr_text:
            logger.info(f"[embedding/doc] Photo {photo_id}: skipping (not a doc or no OCR text)")
            return

        db_lang = SessionLocal()
        try:
            lang = get_setting(db_lang, "default_language") or Main_Settings().DEFAULT_LANGUAGE
        finally:
            db_lang.close()
        doc_text_en = await call_translation_model(ocr_text, backward=True, target_lang=lang)
        embedding = await call_embedding_model(text=doc_text_en, purpose="save")
        await asyncio.to_thread(_save_embedding_sync, photo_id, embedding)
        logger.info(f"[embedding/doc] Photo {photo_id}: doc vector saved ✓")
