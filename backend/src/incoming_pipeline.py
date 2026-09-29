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

from src.config import TaskQueue_Settings
from src.pipeline_tracker import (
    create_pipeline_run,
    finalize_pipeline_run,
    get_task_outcome,
    init_pipeline_tasks,
    mark_task_skipped,
    pipeline_run_context,
    track_task,
)


def _log_phase_results(photo_id: int, phase: str, results: list) -> None:
    """Log any exceptions returned by asyncio.gather(return_exceptions=True)."""
    for r in results:
        if isinstance(r, Exception):
            logger.error(f"[pipeline] photo={photo_id} {phase} task failed: {type(r).__name__}: {r}")


from src.tasks.clip_tasks import (
    auto_tag_clip_task,
    categorize_photo_task,
    compute_perceptual_hashes_task,
    metadata_task,
)
from src.tasks.embedding_tasks import embedding_document_text_task, final_embedding_task
from src.tasks.quality_tasks import (
    blur_task,
    brightness_task,
    edge_density_task,
    entropy_task,
    screenshot_detect_task,
)
from src.tasks.translation_tasks import translate_description_task
from src.tasks.vision_tasks import is_this_document_task, ocr_task, vision_task

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


_TASK_RUNNERS = {
    "metadata_task": metadata_task,
    "compute_perceptual_hashes_task": compute_perceptual_hashes_task,
    "brightness_task": brightness_task,
    "edge_density_task": edge_density_task,
    "blur_task": blur_task,
    "entropy_task": entropy_task,
    "auto_tag_clip_task": auto_tag_clip_task,
    "categorize_photo_task": categorize_photo_task,
    "vision_task": vision_task,
    "final_embedding_task": final_embedding_task,
    "is_this_document_task": is_this_document_task,
    "translate_description_task": translate_description_task,
    "ocr_task": ocr_task,
    "screenshot_detect_task": screenshot_detect_task,
    "embedding_document_text_task": embedding_document_text_task,
}


def _mark_run_running(photo_id, run_id):
    from datetime import datetime, timezone

    from src.models import PipelineRun
    from src.pipeline_tracker import SessionLocal

    with SessionLocal() as db:
        run = db.get(PipelineRun, run_id)
        if run is None or run.photo_id != photo_id:
            raise ValueError("Pipeline run does not belong to this photo")
        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        db.commit()


async def retry_pipeline_task(photo_id: int, task_name: str, *, run_id: int | None = None) -> None:
    """Append a retry run and refresh dependent outputs without clearing good results."""
    if task_name not in _TASK_RUNNERS:
        raise ValueError(f"Unsupported pipeline task: {task_name}")
    run_id = run_id if run_id is not None else create_pipeline_run(photo_id, f"retry:{task_name}")
    _mark_run_running(photo_id, run_id)
    selected = {task_name}
    for phase, names in _PHASES.items():
        for name in names:
            if any(dependency in selected for dependency in _DEPENDENCIES.get(name, [])):
                selected.add(name)
    with pipeline_run_context(run_id):
        for phase, names in _PHASES.items():
            names = [name for name in names if name in selected]
            init_pipeline_tasks(photo_id, phase, names)
            results = await asyncio.gather(
                *[_run_task(photo_id, phase, name, _TASK_RUNNERS[name]) for name in names],
                return_exceptions=True,
            )
            _log_phase_results(photo_id, phase, results)
    finalize_pipeline_run(run_id)


def is_retryable_pipeline_task(task_name: str) -> bool:
    return task_name in _TASK_RUNNERS


_PHASES = {
    "phase_0": _PHASE_0_TASKS,
    "phase_1": _PHASE_1_TASKS,
    "phase_2": _PHASE_2_TASKS,
    "phase_3": _PHASE_3_TASKS,
    "phase_4": _PHASE_4_TASKS,
}
_TASK_PHASES = {name: phase for phase, names in _PHASES.items() for name in names}
_DEPENDENCIES = {
    "translate_description_task": ["vision_task"],
    "final_embedding_task": ["vision_task"],
    "ocr_task": ["is_this_document_task"],
    "embedding_document_text_task": ["ocr_task"],
}


async def _run_task(photo_id, phase, name, runner):
    for dependency in _DEPENDENCIES.get(name, []):
        status, required = get_task_outcome(photo_id, _TASK_PHASES[dependency], dependency)
        if status is not None and status != "done":
            mark_task_skipped(
                photo_id, phase, name, f"Prerequisite {dependency}: {status}", required=required or status != "skipped"
            )
            return
    async with track_task(photo_id, phase, name):
        await runner(photo_id)


async def start_pipeline(photo_id: int, folder_scanner_id: int = None, *, run_id: int | None = None) -> None:
    """Execute all phases under one persistent run, retaining independent results."""
    run_id = run_id if run_id is not None else create_pipeline_run(photo_id, "manual")
    _mark_run_running(photo_id, run_id)
    with pipeline_run_context(run_id):
        for phase, names in _PHASES.items():
            init_pipeline_tasks(photo_id, phase, names)
            results = await asyncio.gather(
                *[_run_task(photo_id, phase, name, globals()[name]) for name in names],
                return_exceptions=True,
            )
            _log_phase_results(photo_id, phase, results)
    outcome = finalize_pipeline_run(run_id)

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

    logger.info(f"[pipeline] photo={photo_id} run={run_id} outcome={outcome}")


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
    logger.info(f"[pipeline] batch: {len(photo_ids)} photos, max_concurrent={max_concurrent}")

    async def _guarded(photo_id: int) -> None:
        async with sem:
            await start_pipeline(photo_id, folder_scanner_id)

    await asyncio.gather(*[_guarded(pid) for pid in photo_ids], return_exceptions=True)
