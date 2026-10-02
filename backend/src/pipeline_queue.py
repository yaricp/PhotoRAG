"""SQLite-backed admission shared by watcher, API and scanner processes."""

import json
from datetime import datetime
from urllib.parse import urlparse

from sqlalchemy import text

from src.config import TaskQueue_Settings
from src.db.database import SessionLocal
from src.models import AIModelConfig, Photo, PipelineQueueEntry, PipelineRun, PipelineTask

ACTIVE = ("queued", "running")


class PipelineRunNotFound(ValueError):
    """Raised when a pipeline run ID does not exist."""


class PipelineRunNotResumable(ValueError):
    """Raised when a run is not paused or interrupted."""


def _lane(db):
    configs = db.query(AIModelConfig).filter(AIModelConfig.type != "chat").all()
    for config in configs:
        if config.mode == "remote" and config.model_provider == "ollama":
            host = urlparse(config.url or "http://localhost:11434").hostname
            if host in ("localhost", "127.0.0.1", "::1"):
                return "local-ollama"
    return "other"


def collect_retryable_tasks(db):
    """Return the latest unfinished task names per inactive photo.

    Successful outcomes supersede older failures. A skipped task is eligible
    only when it was skipped because a prerequisite failed or stopped; other
    inapplicable skips, paused/canceled work, and currently active photos are
    left alone.
    """
    from src.incoming_pipeline import _PHASES, is_retryable_pipeline_task

    active_photos = {
        photo_id
        for (photo_id,) in db.query(PipelineRun.photo_id).filter(PipelineRun.status.in_(ACTIVE)).distinct().all()
    }
    rows = (
        db.query(PipelineTask, PipelineRun)
        .join(PipelineRun, PipelineRun.id == PipelineTask.run_id)
        .order_by(PipelineTask.id)
        .all()
    )
    latest_by_task = {}
    tasks_by_run_and_name = {}
    for task, run in rows:
        latest_by_task[(task.photo_id, task.task_name)] = (task, run)
        tasks_by_run_and_name[(run.id, task.task_name)] = task

    names_by_photo = {}
    retryable_statuses = {"failed", "interrupted", "pending", "running"}
    for (photo_id, task_name), (task, run) in latest_by_task.items():
        if photo_id in active_photos or run.status in ("paused", "canceled", "cancelled"):
            continue
        if not is_retryable_pipeline_task(task_name):
            continue
        status = (task.status or "").lower()
        is_prerequisite_skip = status == "skipped" and _skip_has_retryable_root(
            task,
            run.id,
            tasks_by_run_and_name,
            retryable_statuses,
        )
        if status not in retryable_statuses and not is_prerequisite_skip:
            continue
        names_by_photo.setdefault(photo_id, set()).add(task_name)

    phase_order = {
        task_name: (phase_index, task_index)
        for phase_index, (phase, task_names) in enumerate(_PHASES.items())
        for task_index, task_name in enumerate(task_names)
    }
    return {
        photo_id: sorted(task_names, key=lambda task_name: phase_order[task_name])
        for photo_id, task_names in sorted(names_by_photo.items())
    }


def _skip_has_retryable_root(task, run_id, tasks_by_run_and_name, retryable_statuses, visited=None):
    """Follow prerequisite skips to the actual task outcome that caused them."""
    reason = task.skip_reason or ""
    if not reason.startswith("Prerequisite "):
        return False

    dependency_name, separator, reported_status = reason.removeprefix("Prerequisite ").partition(": ")
    if not separator or not dependency_name:
        return False
    reported_status = reported_status.lower()
    if reported_status in retryable_statuses:
        return True
    if reported_status != "skipped":
        return False

    dependency = tasks_by_run_and_name.get((run_id, dependency_name))
    if dependency is None:
        return False

    visited = visited or set()
    if dependency_name in visited:
        return False
    visited.add(dependency_name)

    dependency_status = (dependency.status or "").lower()
    if dependency_status in retryable_statuses:
        return True
    if dependency_status == "skipped":
        return _skip_has_retryable_root(
            dependency,
            run_id,
            tasks_by_run_and_name,
            retryable_statuses,
            visited,
        )
    return False


def enqueue_photo_run(
    photo_id,
    source,
    folder_scanner_id=None,
    *,
    retry_task_name=None,
    retry_task_names=None,
    clear_outputs=False,
    return_created=False,
):
    """Return the admitted run ID, or the existing active run for duplicate input."""
    if retry_task_name and retry_task_names:
        raise ValueError("Specify one retry task or a retry task set, not both")
    with SessionLocal() as db:
        db.execute(text("BEGIN IMMEDIATE"))
        if db.get(Photo, photo_id) is None:
            raise ValueError(f"Photo {photo_id} not found")
        existing = (
            db.query(PipelineRun).filter(PipelineRun.photo_id == photo_id, PipelineRun.status.in_(ACTIVE)).first()
        )
        if existing:
            return (existing.id, False) if return_created else existing.id
        run = PipelineRun(photo_id=photo_id, source=source, status="queued")
        db.add(run)
        db.flush()
        db.add(
            PipelineQueueEntry(
                run_id=run.id,
                lane=_lane(db),
                folder_scanner_id=folder_scanner_id,
                retry_task_name=retry_task_name,
                retry_task_names=json.dumps(retry_task_names) if retry_task_names else None,
                clear_outputs=clear_outputs,
            )
        )
        run_id = run.id
        db.commit()
        return (run_id, True) if return_created else run_id


def enqueue_retryable_tasks(source="retry"):
    """Admit one bounded retry run per photo for its latest eligible tasks."""
    with SessionLocal() as db:
        retryable_by_photo = collect_retryable_tasks(db)

    run_ids = []
    queued_tasks = 0
    for photo_id, task_names in retryable_by_photo.items():
        run_id, created = enqueue_photo_run(
            photo_id,
            source,
            retry_task_names=task_names,
            return_created=True,
        )
        if created:
            run_ids.append(run_id)
            queued_tasks += len(task_names)
    return {
        "queued_photos": len(run_ids),
        "queued_tasks": queued_tasks,
        "run_ids": run_ids,
    }


def get_retryable_task_counts():
    with SessionLocal() as db:
        retryable_by_photo = collect_retryable_tasks(db)
    return {
        "eligible_photos": len(retryable_by_photo),
        "eligible_tasks": sum(len(task_names) for task_names in retryable_by_photo.values()),
    }


def enqueue_startup_retries():
    """Honor the persisted startup retry preference once per backend launch."""
    from src.db_service import get_setting

    with SessionLocal() as db:
        value = get_setting(db, "retry_unfinished_at_startup")
    enabled = (value or "").strip().lower() in {"1", "true", "yes", "on"}
    if not enabled:
        return {"enabled": False, "queued_photos": 0, "queued_tasks": 0, "run_ids": []}
    return {"enabled": True, **enqueue_retryable_tasks(source="startup-retry")}


def claim_next_run():
    """Atomically claim the oldest eligible run; local Ollama permits one owner."""
    with SessionLocal() as db:
        db.execute(text("BEGIN IMMEDIATE"))
        current_lane = _lane(db)
        queued_ids = db.query(PipelineRun.id).filter(PipelineRun.status == "queued")
        db.query(PipelineQueueEntry).filter(PipelineQueueEntry.run_id.in_(queued_ids)).update(
            {PipelineQueueEntry.lane: current_lane}, synchronize_session=False
        )
        running = db.query(PipelineQueueEntry.lane).join(PipelineRun).filter(PipelineRun.status == "running").all()
        local_busy = (
            bool(running) if current_lane == "local-ollama" else any(lane == "local-ollama" for (lane,) in running)
        )
        query = db.query(PipelineRun).join(PipelineQueueEntry).filter(PipelineRun.status == "queued")
        if local_busy:
            query = query.filter(PipelineQueueEntry.lane != "local-ollama")
        if sum(lane != "local-ollama" for (lane,) in running) >= max(1, TaskQueue_Settings().MAX_CONCURRENT_PIPELINES):
            query = query.filter(PipelineQueueEntry.lane == "local-ollama")
        run = query.order_by(PipelineRun.id).first()
        if run is None:
            return None
        run.status = "running"
        run.started_at = datetime.utcnow()
        db.flush()
        db.expunge(run)
        db.commit()
        return run


def resume_run(run_id):
    """Create a selected replacement run, retaining the interrupted attempt."""
    with SessionLocal() as db:
        old = db.get(PipelineRun, run_id)
        if old is None:
            raise PipelineRunNotFound(f"Run {run_id} not found")
        if old.status not in ("interrupted", "paused"):
            raise PipelineRunNotResumable("Only interrupted or paused runs can be resumed")
        entry = db.get(PipelineQueueEntry, run_id)
        return enqueue_photo_run(
            old.photo_id,
            "resume",
            entry.folder_scanner_id if entry else None,
            retry_task_name=entry.retry_task_name if entry else None,
            retry_task_names=(json.loads(entry.retry_task_names) if entry and entry.retry_task_names else None),
            clear_outputs=entry.clear_outputs if entry else False,
        )


def initialize_queue(bind):
    """Own the backend lifecycle before recovery; caller closes after workers drain.

    A separate SQLite exclusive transaction provides a cross-platform OS-released
    lock without blocking writes to the application database. Never unlink this
    sidecar: other processes must contend on the same file.
    """
    import sqlite3
    from pathlib import Path

    from sqlalchemy.orm import Session

    from src.db.database import migrate_pipeline_runs
    from src.pipeline_tracker import recover_interrupted_pipelines

    database = bind.url.database
    if not database or database == ":memory:":
        raise ValueError("Pipeline lifecycle ownership requires a file-backed database")
    owner = sqlite3.connect(str(Path(database).resolve()) + ".pipeline-owner.sqlite3", timeout=0)
    try:
        owner.execute("BEGIN EXCLUSIVE")
    except sqlite3.OperationalError as exc:
        owner.close()
        raise RuntimeError(
            "Another backend already owns this photo-processing database. "
            "Close the other application instance before starting this one."
        ) from exc
    try:
        migrate_pipeline_runs(bind)
        PipelineQueueEntry.__table__.create(bind, checkfirst=True)
        _migrate_queue_entry_columns(bind)
        with Session(bind) as db:
            recover_interrupted_pipelines(db)
    except BaseException:
        owner.close()
        raise
    return owner


def _migrate_queue_entry_columns(bind):
    """Add new retry intent fields to queue tables from earlier releases."""
    from sqlalchemy import inspect

    if "pipeline_queue_entries" not in inspect(bind).get_table_names():
        return
    columns = {column["name"] for column in inspect(bind).get_columns("pipeline_queue_entries")}
    if "retry_task_names" not in columns:
        with bind.begin() as conn:
            conn.exec_driver_sql("ALTER TABLE pipeline_queue_entries ADD COLUMN retry_task_names TEXT")


async def execute_claimed_run(run):
    """Execute admitted intent; turn unexpected executor failures into outcomes."""
    import asyncio

    from src.models import PhotoCategory, PhotoTag

    try:
        with SessionLocal() as db:
            entry = db.get(PipelineQueueEntry, run.id)
            retry_task_name = entry.retry_task_name
            retry_task_names = entry.retry_task_names
            scanner_id = entry.folder_scanner_id
            if entry.clear_outputs:
                db.query(PhotoTag).filter_by(photo_id=run.photo_id).delete()
                db.query(PhotoCategory).filter_by(photo_id=run.photo_id).delete()
                db.commit()
        if retry_task_names:
            from src.incoming_pipeline import retry_pipeline_tasks

            await retry_pipeline_tasks(run.photo_id, json.loads(retry_task_names), run_id=run.id)
        elif retry_task_name:
            from src.incoming_pipeline import retry_pipeline_task

            await retry_pipeline_task(run.photo_id, retry_task_name, run_id=run.id)
        else:
            from src.incoming_pipeline import start_pipeline

            await start_pipeline(run.photo_id, scanner_id, run_id=run.id)
    except (Exception, asyncio.CancelledError) as exc:
        with SessionLocal() as db:
            stored = db.get(PipelineRun, run.id)
            stored.status = "interrupted" if isinstance(exc, asyncio.CancelledError) else "completed-with-errors"
            stored.summary = str(exc)[:2000] or "Processing interrupted"
            stored.finished_at = datetime.utcnow()
            db.query(PipelineTask).filter(
                PipelineTask.run_id == run.id, PipelineTask.status.in_(["pending", "running"])
            ).update({PipelineTask.status: "interrupted", PipelineTask.finished_at: stored.finished_at})
            db.commit()
        if isinstance(exc, asyncio.CancelledError):
            raise


async def run_scheduler():
    """Backend-owned polling consumer; producers in other processes only enqueue."""
    import asyncio

    from loguru import logger

    tasks = set()
    try:
        while True:
            try:
                run = claim_next_run()
            except Exception:
                logger.exception("[pipeline queue] Claim failed; retrying")
                run = None
            if run is None:
                await asyncio.sleep(0.2)
                continue
            task = asyncio.create_task(execute_claimed_run(run))
            tasks.add(task)
            task.add_done_callback(tasks.discard)
            await asyncio.sleep(0)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


def get_queue_details(run_id):
    """One-based FIFO position and elapsed wait for processing views."""
    with SessionLocal() as db:
        run = db.get(PipelineRun, run_id)
        if run is None:
            raise ValueError(f"Run {run_id} not found")
        position = None
        if run.status == "queued":
            position = db.query(PipelineRun).filter(PipelineRun.status == "queued", PipelineRun.id <= run.id).count()
        end = run.started_at or run.finished_at or datetime.utcnow()
        return {"position": position, "wait_seconds": max(0, (end - run.created_at).total_seconds())}
