from loguru import logger
from src.ai.registry import registry
from src.database import SessionLocal
from src.db_service import get_photo_by_id, delete_job
from src.vector_db_services import store_photo_embedding
from src.models import Photo, Geoposition
from src.ai.prompts import build_photo_text_for_embedding
from src.queues.embedding_queue import embedding_queue


@embedding_queue.task()
def final_embedding_task(photo_id: int, phase: str, folder_scanner_id: int = None):
    """
    Embedding: aggregate the results of all previous tasks
    and save a 768-dimensional vector for search.
    Started in the 'second' phase — after all tasks in the 'first' phase are completed.
    """
    logger.info(f"[embedding] Start embedding task: photo_id={photo_id}, phase={phase}")
    from src.tasks.utils import _finish_task
    db = SessionLocal()
    try:
        photo = get_photo_by_id(db, photo_id)
        if not photo:
            db.rollback()
            db.close()
            _finish_task(
                photo_id=photo_id,
                phase=phase,
                name="final_embedding_task",
                folder_scanner_id=folder_scanner_id
            )
            return

        tags = [pt.tag.name for pt in photo.tags_rel]
        categories = [pc.category.name for pc in photo.categories_rel]
        geo = db.query(Geoposition).filter_by(photo_id=photo_id).first()
        location = geo.address if geo and geo.address else "Unknown Location"

        photo_text = build_photo_text_for_embedding(
            description=photo.description,
            tags=tags,
            categories=categories,
            location=location,
        )
        logger.info(f"[embedding] Photo {photo_id}: embedding text ready")
        logger.info(f"[embedding] Text for embedding: {photo_text}")

        embedding = registry.embedder_encode_text(text=photo_text, purpose="save")
        store_photo_embedding(db, photo.id, embedding, registry.nomic_embedder.name)
        db.commit()
        logger.info(f"[embedding] Photo {photo_id}: vector saved ✓")
        _finish_task(
            photo_id=photo_id,
            phase=phase,
            name="final_embedding_task",
            folder_scanner_id=folder_scanner_id
        )
    except Exception as e:
        logger.error(f"[embedding] Error for photo {photo_id}: {e}")
        db.rollback()  # ✅ ОБЯЗАТЕЛЬНО

        try:
            delete_job(db, photo_id, phase)
            db.commit()  # отдельная транзакция
        except Exception:
            db.rollback()
            logger.error(f"[embedding] Failed to delete job for photo {photo_id}")
            raise
    finally:
        db.close()


@embedding_queue.task()
def embedding_document_text_task(photo_id: int, phase: str, folder_scanner_id: int = None):
    """
    Embedding: aggregate the results of all previous tasks
    and save a 768-dimensional vector for search.
    Started in the 'second' phase — after all tasks in the 'first' phase are completed.
    """
    logger.info(f"[embedding] Start embedding document text task: photo_id={photo_id}, phase={phase}")
    from src.tasks.utils import _finish_task

    db = SessionLocal()
    try:
        photo = get_photo_by_id(db, photo_id)
        if not photo:
            logger.info(f"[embedding] Document {photo_id}: photo not found")
            db.rollback()
            db.close()
            _finish_task(
                photo_id=photo_id,
                phase=phase,
                name="embedding_document_text_task",
                folder_scanner_id=folder_scanner_id
            )
            return
        logger.debug(f"[embedding] type of photo.is_doc: {type(photo.is_doc)}, value {photo.is_doc}")
        if not photo.is_doc:
            logger.info(f"[embedding] Document {photo_id}: not a document")
            db.rollback()
            db.close()
            _finish_task(
                photo_id=photo_id,
                phase=phase,
                name="embedding_document_text_task",
                folder_scanner_id=folder_scanner_id
            )
            return
        doc_text = photo.ocr_text
        if not doc_text:
            logger.info(f"[embedding] Document {photo_id}: no ocr text")
            db.rollback()
            db.close()
            _finish_task(
                photo_id=photo_id,
                phase=phase,
                name="embedding_document_text_task",
                folder_scanner_id=folder_scanner_id
            )
            return
        logger.info(f"[embedding] Document {photo_id}: embedding text ready")
        logger.info(f"[embedding] Text for embedding: {doc_text}")

        doc_text_en = registry.translator.translate(doc_text, backward=True)
        logger.info(f"[embedding] Document {photo_id}: translated to English")

        embedding = registry.embedder_encode_text(text=doc_text_en, purpose="save")
        logger.info(f"[embedding] Document {photo_id}: embedding ready")

        store_photo_embedding(db, photo.id, embedding, registry.nomic_embedder.name)
        logger.info(f"[embedding] Document {photo_id}: embedding stored")
        
        db.commit()
        logger.info(f"[embedding] Document {photo_id}: transaction committed")
        logger.info(f"[embedding] Photo {photo_id}: vector saved ✓")
        _finish_task(
            photo_id=photo_id,
            phase=phase,
            name="embedding_document_text_task",
            folder_scanner_id=folder_scanner_id
        )
    except Exception as e:
        logger.error(f"[embedding] Error for photo {photo_id}: {e}")
        db.rollback()  # ✅ ОБЯЗАТЕЛЬНО

        try:
            delete_job(db, photo_id, phase)
            db.commit()  # отдельная транзакция
        except Exception:
            db.rollback()
            logger.error(f"[embedding] Failed to delete job for photo {photo_id}")
            raise
    finally:
        db.close()