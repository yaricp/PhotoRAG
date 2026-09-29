"""SQLite-backed admission shared by watcher, API and scanner processes."""

from datetime import datetime
from urllib.parse import urlparse

from sqlalchemy import text

from src.config import TaskQueue_Settings
from src.db.database import SessionLocal
from src.models import AIModelConfig, Photo, PipelineQueueEntry, PipelineRun

ACTIVE = ("queued", "running")


def _lane(db):
    configs = db.query(AIModelConfig).filter(AIModelConfig.type != "chat").all()
    for config in configs:
        if config.mode == "remote" and config.model_provider == "ollama":
            host = urlparse(config.url or "http://localhost:11434").hostname
            if host in ("localhost", "127.0.0.1", "::1"):
                return "local-ollama"
    return "other"


def enqueue_photo_run(photo_id, source, folder_scanner_id=None, *, retry_task_name=None, clear_outputs=False):
    """Return the admitted run ID, or the existing active run for duplicate input."""
    with SessionLocal() as db:
        db.execute(text("BEGIN IMMEDIATE"))
        if db.get(Photo, photo_id) is None:
            raise ValueError(f"Photo {photo_id} not found")
        existing = (
            db.query(PipelineRun).filter(PipelineRun.photo_id == photo_id, PipelineRun.status.in_(ACTIVE)).first()
        )
        if existing:
            return existing.id
        run = PipelineRun(photo_id=photo_id, source=source, status="queued")
        db.add(run)
        db.flush()
        db.add(
            PipelineQueueEntry(
                run_id=run.id,
                lane=_lane(db),
                folder_scanner_id=folder_scanner_id,
                retry_task_name=retry_task_name,
                clear_outputs=clear_outputs,
            )
        )
        run_id = run.id
        db.commit()
        return run_id


def claim_next_run():
    """Atomically claim the oldest eligible run; local Ollama permits one owner."""
    with SessionLocal() as db:
        db.execute(text("BEGIN IMMEDIATE"))
        running = db.query(PipelineQueueEntry.lane).join(PipelineRun).filter(PipelineRun.status == "running").all()
        local_busy = any(lane == "local-ollama" for (lane,) in running)
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
            raise ValueError(f"Run {run_id} not found")
        if old.status not in ("interrupted", "paused"):
            raise ValueError("Only interrupted or paused runs can be resumed")
        entry = db.get(PipelineQueueEntry, run_id)
        return enqueue_photo_run(
            old.photo_id,
            "resume",
            entry.folder_scanner_id if entry else None,
            retry_task_name=entry.retry_task_name if entry else None,
            clear_outputs=entry.clear_outputs if entry else False,
        )


def initialize_queue(bind):
    """Upgrade first, then interrupt old work before any watchers can submit."""
    from sqlalchemy.orm import Session

    from src.db.database import migrate_pipeline_runs
    from src.pipeline_tracker import recover_interrupted_pipelines

    migrate_pipeline_runs(bind)
    PipelineQueueEntry.__table__.create(bind, checkfirst=True)
    with Session(bind) as db:
        recover_interrupted_pipelines(db)


async def execute_claimed_run(run):
    """Execute admitted intent; turn unexpected executor failures into outcomes."""
    import asyncio

    from src.models import PhotoCategory, PhotoTag

    try:
        with SessionLocal() as db:
            entry = db.get(PipelineQueueEntry, run.id)
            retry_task_name = entry.retry_task_name
            scanner_id = entry.folder_scanner_id
            if entry.clear_outputs:
                db.query(PhotoTag).filter_by(photo_id=run.photo_id).delete()
                db.query(PhotoCategory).filter_by(photo_id=run.photo_id).delete()
                db.commit()
        if retry_task_name:
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
