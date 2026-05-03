from loguru import logger

from src.ai.registry import registry
from src.database import SessionLocal
from src.db_service import get_photo_by_id, delete_job
from src.ai.ocr import extract_text_from_image

from src.queues.vision_queue import vision_queue


# ---------------------------------------------------------------------------
# Vision tasks → vision_queue (воркер: src.queue.vision_queue)
# ---------------------------------------------------------------------------

@vision_queue.task()
def vision_task(photo_id: int, phase: str):
    """Vision: сгенерировать текстовое описание фото."""
    logger.info(f"[vision] Start vision task: photo_id={photo_id}, phase={phase}")
    from src.tasks.utils import _finish_task
    db = SessionLocal()
    try:
        photo = get_photo_by_id(db, photo_id)
        if not photo:
            db.rollback()
            _finish_task(photo_id=photo_id, phase=phase, name="metadata_task")
            return

        desc = registry.generate_vision_text(
            file_path=photo.file_path,
            prompt_key="describe_scene",
        )
        photo.description = desc
        db.commit()
        logger.info(f"[vision] Photo {photo_id}: description saved ✓")
        _finish_task(photo_id=photo_id, phase=phase, name="vision_task")
    except Exception as e:
        logger.error(f"[vision] Error for photo {photo_id}: {e}")
        db.rollback()  # ✅ ОБЯЗАТЕЛЬНО

        try:
            delete_job(db, photo_id, phase)
            db.commit()  # отдельная транзакция
        except Exception:
            db.rollback()
            logger.error(f"[vision] Failed to delete job for photo {photo_id}")
            raise
    finally:
        db.close()


@vision_queue.task()
def is_this_document_task(photo_id: int, phase: str):
    """Check if the photo is a document"""
    logger.info(f"[vision] Start is_document task: photo_id={photo_id}, phase={phase}")
    from src.tasks.utils import _finish_task
    db = SessionLocal()
    try:
        photo = get_photo_by_id(db, photo_id)
        if not photo:
            db.rollback()
            _finish_task(photo_id=photo_id, phase=phase, name="metadata_task")
            return

        result = registry.generate_vision_text(
            file_path=photo.file_path,
            prompt_key="is_document",
        )
        photo.is_doc = "yes" in result.lower()
        db.commit()
        logger.info(f"[vision] Photo {photo_id}: is_doc={photo.is_doc} ✓")
        _finish_task(photo_id=photo_id, phase=phase, name="is_this_document_task")
    except Exception as e:
        logger.error(f"[vision] Error for photo {photo_id}: {e}")
        db.rollback()  # ✅ ОБЯЗАТЕЛЬНО

        try:
            delete_job(db, photo_id, phase)
            db.commit()  # отдельная транзакция
        except Exception:
            db.rollback()
            logger.error(f"[vision] Failed to delete job for photo {photo_id}")
            raise
    finally:
        db.close()


@vision_queue.task()
def ocr_task(photo_id: int, phase: str):
    """OCR recognition: extract text from image"""
    logger.info(f"[vision] Start ocr task: photo_id={photo_id}, phase={phase}")
    from src.tasks.utils import _finish_task
    db = SessionLocal()
    try:
        photo = get_photo_by_id(db, photo_id)
        if not photo:
            db.rollback()
            _finish_task(photo_id=photo_id, phase=phase, name="metadata_task")
            return

        text = extract_text_from_image(
            photo.file_path,
            lang="rus+eng"
        )
        if text and text.strip():
            photo.ocr_text = text
            db.commit()
            logger.info(f"[ocr] Photo {photo_id}: text extracted, checking if document...")
            # Запускаем vision-проверку документа асинхронно
            is_this_document_task(photo_id, phase)
        db.commit()
        _finish_task(photo_id=photo_id, phase=phase, name="ocr_task")

    except Exception as e:
        logger.error(f"[ocr] Error for photo {photo_id}: {e}")
        db.rollback()  # ✅ ОБЯЗАТЕЛЬНО

        try:
            delete_job(db, photo_id, phase)
            db.commit()  # отдельная транзакция
        except Exception:
            db.rollback()
            logger.error(f"[ocr] Failed to delete job for photo {photo_id}")
            raise
    finally:
        db.close()

