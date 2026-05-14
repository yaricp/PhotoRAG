"""Phase-0 and phase-3 image quality detection tasks — called by incoming_pipeline.py."""
import asyncio
from loguru import logger

from src.db.database import SessionLocal
from src.db_service import get_photo_by_id, create_quality_issue
from src.pipeline_tracker import track_task
from src.quality_checks import (
    check_brightness,
    check_edge_density,
    check_blur,
    check_entropy,
    check_screenshot,
)


def _quality_check_sync(photo_id: int, check_fn, issue_type: str) -> None:
    """Run a single CPU-bound quality check and persist the result."""
    db = SessionLocal()
    try:
        photo = get_photo_by_id(db, photo_id)
        if not photo:
            return
        try:
            flagged, score = check_fn(photo.file_path)
            logger.debug(f"[quality] {issue_type} photo {photo_id}: flagged={flagged}, score={score}")
            if flagged:
                create_quality_issue(db, photo.id, issue_type, score)
                logger.info(f"[quality] Photo {photo_id} flagged '{issue_type}' (score={score})")
            db.commit()
        except Exception as check_err:
            logger.warning(f"[quality] {issue_type} check failed for photo {photo_id}: {check_err} — skipping")
            db.rollback()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def _quality_task(photo_id: int, phase: str, task_name: str, check_fn, issue_type: str) -> None:
    async with track_task(photo_id, phase, task_name):
        await asyncio.to_thread(_quality_check_sync, photo_id, check_fn, issue_type)


async def brightness_task(photo_id: int) -> None:
    """Flag photos with abnormal brightness."""
    await _quality_task(photo_id, "phase_0", "brightness_task", check_brightness, "brightness")


async def edge_density_task(photo_id: int) -> None:
    """Flag featureless photos with very low edge density."""
    await _quality_task(photo_id, "phase_0", "edge_density_task", check_edge_density, "edge_density")


async def blur_task(photo_id: int) -> None:
    """Flag blurry photos via Laplacian variance."""
    await _quality_task(photo_id, "phase_0", "blur_task", check_blur, "blur")


async def entropy_task(photo_id: int) -> None:
    """Flag low-information photos via image entropy."""
    await _quality_task(photo_id, "phase_0", "entropy_task", check_entropy, "entropy")


async def screenshot_detect_task(photo_id: int) -> None:
    """Flag screenshots and UI captures."""
    await _quality_task(photo_id, "phase_3", "screenshot_detect_task", check_screenshot, "screenshot")
