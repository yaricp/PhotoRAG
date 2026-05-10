from loguru import logger
from sqlalchemy import text

from src.database import SessionLocal
from src.db_service import (
    delete_job, get_or_create_job, get_folder_scanner, update_folder_scanner_progress
)


def phase_logic(phase: str) -> tuple[str, str]:
    """
    Фазы пайплайна:
      init   → first:  параллельные задачи (metadata, clip, vision)
      first  → second: финальный эмбеддинг (ждёт результатов первой фазы)
      second → third:  OCR (опционально)
    """
    if phase == "init":
        return "first", (
            "metadata_task,auto_tag_clip_task,categorize_photo_task,"
            "vision_task,ocr_task,compute_perceptual_hashes_task,"
            "brightness_task,edge_density_task,blur_task,entropy_task,"
        )
    elif phase == "first":
        return "second", "final_embedding_task,translate_description_task,is_this_document_task,"
    elif phase == "second":
        return "third", "embedding_document_text_task,screenshot_detect_task,"
    return "", ""


def _dispatch_tasks(
    photo_id: int, phase: str, tasks: str, folder_scanner_id: int = None
):
    """Send tasks to the appropriate queues."""
    from .clip_tasks import auto_tag_clip_task, metadata_task, categorize_photo_task, compute_perceptual_hashes_task
    from .vision_tasks import vision_task, ocr_task, is_this_document_task
    from .embedding_tasks import final_embedding_task, embedding_document_text_task
    from .translation_tasks import translate_description_task
    from .quality_tasks import brightness_task, edge_density_task, blur_task, entropy_task, screenshot_detect_task
    
    for task_name in tasks.split(","):
        task_name = task_name.strip()
        if not task_name:
            continue

        if task_name == "metadata_task":
            metadata_task(photo_id, phase=phase, folder_scanner_id=folder_scanner_id)
        elif task_name == "auto_tag_clip_task":
            auto_tag_clip_task(photo_id, phase=phase, folder_scanner_id=folder_scanner_id)
        elif task_name == "categorize_photo_task":
            categorize_photo_task(photo_id, phase=phase, folder_scanner_id=folder_scanner_id)
        elif task_name == "vision_task":
            vision_task(photo_id, phase=phase, folder_scanner_id=folder_scanner_id)
        elif task_name == "final_embedding_task":
            final_embedding_task(photo_id, phase=phase, folder_scanner_id=folder_scanner_id)
        elif task_name == "ocr_task":
            ocr_task(photo_id, phase=phase, folder_scanner_id=folder_scanner_id)
        elif task_name == "is_this_document_task":
            is_this_document_task(photo_id, phase=phase, folder_scanner_id=folder_scanner_id)
        elif task_name == "embedding_document_text_task":
            embedding_document_text_task(photo_id, phase=phase, folder_scanner_id=folder_scanner_id)
        elif task_name == "translate_description_task":
            translate_description_task(photo_id, phase=phase, folder_scanner_id=folder_scanner_id)
        elif task_name == "compute_perceptual_hashes_task":
            compute_perceptual_hashes_task(photo_id, phase=phase, folder_scanner_id=folder_scanner_id)
        elif task_name == "brightness_task":
            brightness_task(photo_id, phase=phase, folder_scanner_id=folder_scanner_id)
        elif task_name == "edge_density_task":
            edge_density_task(photo_id, phase=phase, folder_scanner_id=folder_scanner_id)
        elif task_name == "blur_task":
            blur_task(photo_id, phase=phase, folder_scanner_id=folder_scanner_id)
        elif task_name == "entropy_task":
            entropy_task(photo_id, phase=phase, folder_scanner_id=folder_scanner_id)
        elif task_name == "screenshot_detect_task":
            screenshot_detect_task(photo_id, phase=phase, folder_scanner_id=folder_scanner_id)

        logger.info(f"[pipeline] Dispatched {task_name} for photo {photo_id}")


def _finish_task(
    photo_id: int, phase: str, name: str, folder_scanner_id: int = None
):
    """
    Finish task in phase and start next phase if needed
    """
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
        logger.info(f"[pipeline] Tasks row for photo {photo_id} and phase {phase}: {tasks_row}")
        if tasks_row is None:
            logger.info(f"[pipeline] No tasks row for photo {photo_id} and phase {phase}")
            return

        remaining = (tasks_row or "").strip()

        logger.info(f"[pipeline] Task {name} done. Remaining: '{remaining}' and phase {phase}")

        if remaining == "":
            delete_job(db, photo_id, phase)
            _start_next_phase(photo_id, phase, folder_scanner_id)

    except Exception as e:
        logger.error(f"[pipeline] _finish_task failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def _start_next_phase(
    photo_id: int, phase: str, folder_scanner_id: int = None
):
    """
    Start next phase if needed
    """
    logger.info(f"[pipeline] Next phase for folder scanner {folder_scanner_id}")
    db = SessionLocal()
    try:
        next_phase, new_tasks = phase_logic(phase)
        if folder_scanner_id:
            
            folder_scanner = get_folder_scanner(db, folder_scanner_id)
            logger.info(f"[pipeline] Folder scanner {folder_scanner.id}")
            if folder_scanner:
                update_folder_scanner_progress(db, folder_scanner_id)
                logger.info(f"[pipeline] Folder scanner {folder_scanner_id} progress updated")
        if not next_phase:
            logger.info(f"[pipeline] FINISHED processing for photo {photo_id}")   
            db.commit()
            db.close()
            return
        
        get_or_create_job(db, photo_id=photo_id, phase=next_phase, tasks=new_tasks)
        db.commit()
        logger.info(f"[pipeline] New JOB created: {next_phase} for photo {photo_id}")
        _dispatch_tasks(photo_id, next_phase, new_tasks, folder_scanner_id)

    except Exception as e:
        db.rollback()
        logger.error(f"[pipeline] start_next_phase failed: {e}")
        raise
    finally:
        db.close()


# def run_task_logic(fn, photo_id, phase, task_name):
#     """
#     Run task logic
#     """
#     db = SessionLocal()
#     try:
#         result = fn(db, photo_id)

#         db.commit()

#         _finish_task(photo_id=photo_id, phase=phase, name=task_name)

#     except Exception as e:
#         logger.error(f"[{task_name}] Error for photo {photo_id}: {e}")
#         db.rollback()

#         try:
#             delete_job(db, photo_id, phase)
#             db.commit()
#         except Exception:
#             db.rollback()
#             raise
#     finally:
#         db.close()