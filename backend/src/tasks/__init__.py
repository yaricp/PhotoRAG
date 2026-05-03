from loguru import logger

from src.database import SessionLocal
from src.db_service import get_or_create_job, delete_job

from .utils import phase_logic, _dispatch_tasks


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
