from loguru import logger
from src.ai.registry import registry
from src.database import SessionLocal
from src.db_service import get_photo_by_id, delete_job
from src.vector_db_services import store_photo_embedding
from src.models import Photo, Geoposition
from src.ai.prompts import build_photo_text_for_embedding
from src.queues.embedding_queue import embedding_queue


@embedding_queue.task()
def final_embedding_task(photo_id: int, phase: str):
    """
    Embedding: агрегировать результаты всех предыдущих задач
    и сохранить 768-мерный вектор для поиска.
    Запускается в фазе 'second' — после завершения всех задач фазы 'first'.
    """
    from src.tasks import _finish_task
    db = SessionLocal()
    try:
        photo = get_photo_by_id(db, photo_id)
        if not photo:
            db.rollback()
            db.close()
            _finish_task(photo_id=photo_id, phase=phase, name="metadata_task")
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
        _finish_task(photo_id=photo_id, phase=phase, name="final_embedding_task")
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
