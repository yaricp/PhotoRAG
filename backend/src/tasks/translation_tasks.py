from loguru import logger

from src.ai.registry import registry
from src.database import SessionLocal
from src.db_service import get_photo_by_id, delete_job
from src.queues.translation_queue import translate_queue
from src.config import Main_Settings


# @translate_queue.task()
# def translate_text_task(translate_request: TranslateRequest):
#     """Translates text"""
#     return registry.translator.translate(translate_request)


@translate_queue.task()
def translate_description_task(photo_id: int, phase: str, folder_scanner_id: int = None):
    """
    Translate the photo description to other languages.
    """
    from src.tasks.utils import _finish_task
    
    main_settings = Main_Settings()
    db = SessionLocal()
    try:
        if main_settings.DEFAULT_LANGUAGE == "en":
            _finish_task(
                photo_id=photo_id,
                phase=phase,
                name="translate_description_task",
                folder_scanner_id=folder_scanner_id
            )
            return
        photo = get_photo_by_id(db, photo_id)
        if not photo:
            logger.info(f"[translate] No photo found for photo_id {photo_id}")
            _finish_task(
                photo_id=photo_id,
                phase=phase,
                name="translate_description_task",
                folder_scanner_id=folder_scanner_id
            )
            return

        logger.info(f"[translate] Translating photo {photo_id}")
        translated_description = registry.translator.translate(
            photo.description, backward=False
        )
        photo.translated_description = translated_description
        db.commit()
        logger.info(f"[translate] Translation for photo {photo_id} completed")

        _finish_task(
            photo_id=photo_id,
            phase=phase,
            name="translate_description_task",
            folder_scanner_id=folder_scanner_id
        )
        
    except Exception as e:
        logger.error(f"[translate] Error for photo {photo_id}: {e}")
        # Optional: handle error logic (e.g., retry or mark as failed)
        db.rollback()
        try:
            delete_job(db, photo_id, phase)
            db.commit()  # отдельная транзакция
        except Exception:
            db.rollback()
            logger.error(f"[vision] Failed to delete job for photo {photo_id}")
            raise
    finally:
        db.close()
