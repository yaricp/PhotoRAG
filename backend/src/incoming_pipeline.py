"""
Async incoming photo pipeline.

Phase 0 (parallel, model-free): metadata, perceptual hashes, brightness,
                                 edge density, blur, entropy
                                 → photo visible in gallery immediately after
Phase 1 (parallel, AI models):  CLIP tags, CLIP categories, vision description, OCR
Phase 2 (parallel):             is_document check, description translation, final embedding
Phase 3 (parallel):             document text embedding, screenshot detection

Use `run_pipelines_batch(photo_ids)` to process multiple photos concurrently.
Each photo's phases remain sequential; phases across photos run in parallel,
bounded by `TaskQueue_Settings.MAX_CONCURRENT_PIPELINES`.
"""
import asyncio
from loguru import logger

from src.pipeline_tracker import init_pipeline_tasks
from src.config import TaskQueue_Settings


def _log_phase_results(photo_id: int, phase: str, results: list) -> None:
    """Log any exceptions returned by asyncio.gather(return_exceptions=True)."""
    for r in results:
        if isinstance(r, Exception):
            logger.error(f"[pipeline] photo={photo_id} {phase} task failed: {type(r).__name__}: {r}")
from src.tasks.clip_tasks import (
    metadata_task,
    auto_tag_clip_task,
    categorize_photo_task,
    compute_perceptual_hashes_task,
)
from src.tasks.vision_tasks import vision_task, is_this_document_task, ocr_task
from src.tasks.quality_tasks import brightness_task, edge_density_task, blur_task, entropy_task, screenshot_detect_task
from src.tasks.embedding_tasks import final_embedding_task, embedding_document_text_task
from src.tasks.translation_tasks import translate_description_task

_PHASE_0_TASKS = [
    "metadata_task",
    "compute_perceptual_hashes_task",
    "brightness_task",
    "edge_density_task",
    "blur_task",
    "entropy_task",
]

_PHASE_1_TASKS = [
    "auto_tag_clip_task",
    "categorize_photo_task",
    "vision_task",
]

_PHASE_2_TASKS = [
    "final_embedding_task",
    "is_this_document_task",
    "translate_description_task",
]

_PHASE_3_TASKS = [
    "ocr_task",
    "screenshot_detect_task",
]

_PHASE_4_TASKS = [
    "embedding_document_text_task",
]




async def start_pipeline(photo_id: int, folder_scanner_id: int = None) -> None:
    """
    Run the full async processing pipeline for a single photo.

    Each phase waits for all tasks in the previous phase to complete before
    starting. Within a phase, all tasks run concurrently.
    """
    logger.info(f"[pipeline] Starting for photo {photo_id}")

    # ------------------------------------------------------------------
    # Phase 0 — fast, model-free: makes the photo immediately browsable
    # ------------------------------------------------------------------
    init_pipeline_tasks(photo_id, "phase_0", _PHASE_0_TASKS)
    results = await asyncio.gather(
        metadata_task(photo_id),
        compute_perceptual_hashes_task(photo_id),
        brightness_task(photo_id),
        edge_density_task(photo_id),
        blur_task(photo_id),
        entropy_task(photo_id),
        return_exceptions=True,
    )
    _log_phase_results(photo_id, "phase_0", results)
    logger.info(f"[pipeline] Phase 0 complete for photo {photo_id}")

    # ------------------------------------------------------------------
    # Phase 1 — AI models: CLIP + vision + OCR
    # ------------------------------------------------------------------
    init_pipeline_tasks(photo_id, "phase_1", _PHASE_1_TASKS)
    results = await asyncio.gather(
        auto_tag_clip_task(photo_id),
        categorize_photo_task(photo_id),
        vision_task(photo_id),
        return_exceptions=True,
    )
    _log_phase_results(photo_id, "phase_1", results)
    logger.info(f"[pipeline] Phase 1 complete for photo {photo_id}")

    # ------------------------------------------------------------------
    # Phase 2
    # ------------------------------------------------------------------
    init_pipeline_tasks(photo_id, "phase_2", _PHASE_2_TASKS)
    results = await asyncio.gather(
        final_embedding_task(photo_id),
        is_this_document_task(photo_id),
        translate_description_task(photo_id),
        return_exceptions=True,
    )
    _log_phase_results(photo_id, "phase_2", results)
    logger.info(f"[pipeline] Phase 2 complete for photo {photo_id}")

    # ------------------------------------------------------------------
    # Phase 3
    # ------------------------------------------------------------------
    init_pipeline_tasks(photo_id, "phase_3", _PHASE_3_TASKS)
    results = await asyncio.gather(
        ocr_task(photo_id),
        screenshot_detect_task(photo_id),
        return_exceptions=True,
    )
    _log_phase_results(photo_id, "phase_3", results)
    logger.info(f"[pipeline] Phase 3 complete for photo {photo_id}")

    # ------------------------------------------------------------------
    # Phase 4
    # ------------------------------------------------------------------
    init_pipeline_tasks(photo_id, "phase_4", _PHASE_4_TASKS)
    results = await asyncio.gather(
        embedding_document_text_task(photo_id),
        return_exceptions=True,
    )
    _log_phase_results(photo_id, "phase_4", results)
    logger.info(f"[pipeline] Phase 4 complete for photo {photo_id}")



    # ------------------------------------------------------------------
    # Update folder scanner progress
    # ------------------------------------------------------------------
    if folder_scanner_id is not None:
        from src.db.database import SessionLocal
        from src.db_service import update_folder_scanner_progress
        db = SessionLocal()
        try:
            update_folder_scanner_progress(db, folder_scanner_id)
            db.commit()
        except Exception as exc:
            logger.error(f"[pipeline] Failed to update folder scanner {folder_scanner_id}: {exc}")
            db.rollback()
        finally:
            db.close()

    logger.info(f"[pipeline] FINISHED processing photo {photo_id}")


async def run_pipelines_batch(
    photo_ids: list[int],
    folder_scanner_id: int | None = None,
) -> None:
    """
    Run `start_pipeline` for every photo_id concurrently, bounded by
    MAX_CONCURRENT_PIPELINES.  Phases within each photo remain sequential;
    photos never block each other.
    """
    if not photo_ids:
        return

    max_concurrent = TaskQueue_Settings().MAX_CONCURRENT_PIPELINES
    sem = asyncio.Semaphore(max_concurrent)
    logger.info(
        f"[pipeline] batch: {len(photo_ids)} photos, max_concurrent={max_concurrent}"
    )

    async def _guarded(photo_id: int) -> None:
        async with sem:
            await start_pipeline(photo_id, folder_scanner_id)

    await asyncio.gather(*[_guarded(pid) for pid in photo_ids], return_exceptions=True)
