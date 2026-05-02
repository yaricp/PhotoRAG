from loguru import logger
from sqlalchemy import text

from src.database import SessionLocal

from src.db_service import (
    get_photo_by_id,
    get_or_create_camera,
    update_photo_geoposition,
    add_photo_tag_with_score,
    get_or_create_category,
    add_photo_category_with_score,
    get_or_create_job,
    delete_job
)

from .clip_tasks import auto_tag_clip_task, metadata_task, categorize_photo_task
from .vision_tasks import vision_task, ocr_task, is_this_document_task
from .embedding_tasks import final_embedding_task


def phase_logic(phase: str) -> tuple[str, str]:
    """
    Фазы пайплайна:
      init   → first:  параллельные задачи (metadata, clip, vision)
      first  → second: финальный эмбеддинг (ждёт результатов первой фазы)
      second → third:  OCR (опционально)
    """
    if phase == "init":
        return "first", "metadata_task,auto_tag_clip_task,categorize_photo_task,vision_task,"
    elif phase == "first":
        return "second", "final_embedding_task,"
    elif phase == "second":
        return "third", "ocr_task,"
    return "", ""


def start_pipeline(photo_id: int):
    """Start pipeline for photo."""
    logger.info(f"[pipeline] Starting for photo {photo_id}")
    db = SessionLocal()
    try:
        next_phase, new_tasks = phase_logic("init")
        get_or_create_job(db, photo_id=photo_id, phase=next_phase, tasks=new_tasks)
        logger.info(f"[pipeline] Job created for photo {photo_id}")
        _dispatch_tasks(photo_id=photo_id, phase=next_phase, tasks=new_tasks)
        logger.info(f"[pipeline] Tasks dispatched for photo {photo_id}")
    except Exception as e:
        logger.error(f"[pipeline] Error starting pipeline for photo {photo_id}: {e}")
        delete_job(db, photo_id, "first")
    finally:
        db.close()


def _dispatch_tasks(photo_id: int, phase: str, tasks: str):
    """Отправить задачи в соответствующие очереди."""
    for task_name in tasks.split(","):
        task_name = task_name.strip()
        if not task_name:
            continue

        if task_name == "metadata_task":
            metadata_task(photo_id, phase=phase)
        elif task_name == "auto_tag_clip_task":
            auto_tag_clip_task(photo_id, phase=phase)
        elif task_name == "categorize_photo_task":
            categorize_photo_task(photo_id, phase=phase)
        elif task_name == "vision_task":
            vision_task(photo_id, phase=phase)
        elif task_name == "final_embedding_task":
            final_embedding_task(photo_id, phase=phase)
        elif task_name == "ocr_task":
            ocr_task(photo_id, phase=phase)
        elif task_name == "is_this_document_task":
            is_this_document_task(photo_id, phase=phase)

        logger.info(f"[pipeline] Dispatched {task_name} for photo {photo_id}")


def _finish_task(photo_id: int, phase: str, name: str):
    logger.info(f"[pipeline] Finishing task {name} for photo {photo_id} and phase {phase}")

    db = SessionLocal()
    try:
        # 1. Убираем задачу атомарно
        db.execute(
            text("""
                UPDATE processing_jobs
                SET tasks = TRIM(REPLACE(tasks, :task_name, ''))
                WHERE photo_id = :photo_id
                  AND phase = :phase
            """),
            {
                "task_name": name + ",",
                "photo_id": photo_id,
                "phase": phase,
            }
        )
        db.commit()

        # 2. Читаем состояние В ОТДЕЛЬНОЙ транзакции
        tasks_row = db.execute(
            text("""
                SELECT tasks
                FROM processing_jobs
                WHERE photo_id = :photo_id
                  AND phase = :phase
            """),
            {"photo_id": photo_id, "phase": phase}
        ).scalar_one_or_none()

        if tasks_row is None:
            return

        remaining = (tasks_row or "").strip()

        logger.info(f"[pipeline] Task {name} done. Remaining: '{remaining}' and phase {phase}")

        if remaining == "":
            delete_job(db, photo_id, phase)
            _start_next_phase(photo_id, phase)

    except Exception as e:
        logger.error(f"[pipeline] _finish_task failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def _start_next_phase(photo_id: int, phase: str):
    db = SessionLocal()
    try:
        next_phase, new_tasks = phase_logic(phase)
        if not next_phase:
            return
        logger.info(f"[pipeline] next phase: {next_phase}, new tasks: {new_tasks}")

        db.execute(
            text("""
                INSERT INTO processing_jobs (photo_id, phase, tasks)
                VALUES (:photo_id, :phase, :tasks)
            """),
            {
                "photo_id": photo_id,
                "phase": phase,
                "tasks": new_tasks
            }
        )
        db.commit()
        _dispatch_tasks(photo_id, next_phase, new_tasks)

    except Exception as e:
        db.rollback()
        logger.error(f"[pipeline] start_next_phase failed: {e}")
        raise
    finally:
        db.close()


def run_task_logic(fn, photo_id, phase, task_name):
    db = SessionLocal()
    try:
        result = fn(db, photo_id)

        db.commit()

        _finish_task(photo_id=photo_id, phase=phase, name=task_name)

    except Exception as e:
        logger.error(f"[{task_name}] Error for photo {photo_id}: {e}")
        db.rollback()

        try:
            delete_job(db, photo_id, phase)
            db.commit()
        except Exception:
            db.rollback()
            raise
    finally:
        db.close()