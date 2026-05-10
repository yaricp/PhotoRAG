# backend/src/tasks/quality_tasks.py
"""Phase-1 and phase-3 quality detection tasks — all run on clip_queue (CPU only)."""
from loguru import logger

from src.database import SessionLocal
from src.db_service import get_photo_by_id, delete_job, create_quality_issue
from src.quality_checks import (
    check_brightness,
    check_edge_density,
    check_blur,
    check_entropy,
    check_screenshot,
)
from src.queues.clip_queue import clip_queue


def _run_quality_check(photo_id: int, phase: str, task_name: str, check_fn, issue_type: str, folder_scanner_id=None):
    """Shared runner: open photo, run check_fn, flag if needed, finish task."""
    from src.tasks.utils import _finish_task
    db = SessionLocal()
    try:
        photo = get_photo_by_id(db, photo_id)
        if not photo:
            db.rollback()
            _finish_task(photo_id=photo_id, phase=phase, name=task_name, folder_scanner_id=folder_scanner_id)
            return

        try:
            flagged, score = check_fn(photo.file_path)
            if flagged:
                create_quality_issue(db, photo.id, issue_type, score)
                logger.info(f"[quality] Photo {photo_id} flagged as '{issue_type}' (score={score})")
            db.commit()
        except Exception as check_err:
            logger.warning(f"[quality] {task_name} check failed for photo {photo_id}: {check_err} — skipping")
            db.rollback()

        _finish_task(photo_id=photo_id, phase=phase, name=task_name, folder_scanner_id=folder_scanner_id)

    except Exception as e:
        logger.error(f"[quality] Fatal error in {task_name} for photo {photo_id}: {e}")
        db.rollback()
        try:
            delete_job(db, photo_id, phase)
            db.commit()
        except Exception:
            db.rollback()
            raise
    finally:
        db.close()


@clip_queue.task()
def brightness_task(photo_id: int, phase: str, folder_scanner_id: int = None):
    """Flag photos with abnormal brightness (too dark or overexposed)."""
    _run_quality_check(photo_id, phase, "brightness_task", check_brightness, "brightness", folder_scanner_id)


@clip_queue.task()
def edge_density_task(photo_id: int, phase: str, folder_scanner_id: int = None):
    """Flag featureless / flat photos with very low edge density."""
    _run_quality_check(photo_id, phase, "edge_density_task", check_edge_density, "edge_density", folder_scanner_id)


@clip_queue.task()
def blur_task(photo_id: int, phase: str, folder_scanner_id: int = None):
    """Flag blurry photos via Laplacian variance."""
    _run_quality_check(photo_id, phase, "blur_task", check_blur, "blur", folder_scanner_id)


@clip_queue.task()
def entropy_task(photo_id: int, phase: str, folder_scanner_id: int = None):
    """Flag low-information photos via image entropy."""
    _run_quality_check(photo_id, phase, "entropy_task", check_entropy, "entropy", folder_scanner_id)


@clip_queue.task()
def screenshot_detect_task(photo_id: int, phase: str, folder_scanner_id: int = None):
    """Flag screenshots and UI captures via color-quantization analysis."""
    _run_quality_check(photo_id, phase, "screenshot_detect_task", check_screenshot, "screenshot", folder_scanner_id)
