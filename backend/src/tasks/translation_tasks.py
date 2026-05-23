"""Phase-2 translation task — called by incoming_pipeline.py."""
import asyncio
from loguru import logger

from src.config import Main_Settings
from src.db.database import SessionLocal
from src.db_service import get_photo_by_id, get_setting
from src.model_services import call_translation_model
from src.pipeline_tracker import track_task


def _get_description_sync(photo_id: int) -> str | None:
    db = SessionLocal()
    try:
        photo = get_photo_by_id(db, photo_id)
        return photo.description if photo else None
    finally:
        db.close()


def _save_translation_sync(photo_id: int, translated: str) -> None:
    db = SessionLocal()
    try:
        photo = get_photo_by_id(db, photo_id)
        if photo:
            photo.translated_description = translated
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _get_target_language() -> str:
    """Return the user's target language from DB, falling back to config."""
    db = SessionLocal()
    try:
        return get_setting(db, "default_language") or Main_Settings().DEFAULT_LANGUAGE
    finally:
        db.close()


async def translate_description_task_for_retranslation(photo_id: int, target_lang: str) -> None:
    """
    Re-translate a photo description to target_lang.
    Used by retranslation_pipeline; tracked under phase="retranslation" so it
    appears on the Processing Page separately from the normal ingestion pipeline.
    """
    logger.info(f"[retranslation] Start: photo_id={photo_id} lang={target_lang}")
    async with track_task(photo_id, "retranslation", "translate_description_task"):
        description = await asyncio.to_thread(_get_description_sync, photo_id)
        if not description:
            logger.info(f"[retranslation] Photo {photo_id}: no description, skipping")
            return

        translated = await call_translation_model(description, backward=False, target_lang=target_lang)
        await asyncio.to_thread(_save_translation_sync, photo_id, translated)
        logger.info(f"[retranslation] Photo {photo_id}: translation saved ✓")


async def translate_description_task(photo_id: int) -> None:
    """Translate the photo description into the user's configured language."""
    logger.info(f"[translate] Start: photo_id={photo_id}")
    async with track_task(photo_id, "phase_2", "translate_description_task"):
        lang = await asyncio.to_thread(_get_target_language)
        if lang == "en":
            logger.info(f"[translate] Photo {photo_id}: language is en, skipping")
            return

        description = await asyncio.to_thread(_get_description_sync, photo_id)
        if not description:
            return

        translated = await call_translation_model(description, backward=False, target_lang=lang)
        await asyncio.to_thread(_save_translation_sync, photo_id, translated)
        logger.info(f"[translate] Photo {photo_id}: translation saved ✓")
