"""
Pipeline progress tracker for the Processing Page.

Each async pipeline task wraps its body in `async with track_task(...):`
to update the PipelineTask row in the main DB. The API reads these rows
to show real-time status in the frontend.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.db.database import SessionLocal
from src.models import PipelineTask


def init_pipeline_tasks(photo_id: int, phase: str, task_names: list[str]) -> None:
    """Create one PipelineTask per task_name with status='pending'.

    Existing rows for the same (photo_id, phase) are deleted first so that
    re-runs don't leave stale rows that the tracker would update instead of
    the newly created ones.
    """
    if not task_names:
        return
    db = SessionLocal()
    try:
        db.query(PipelineTask).filter_by(photo_id=photo_id, phase=phase).delete()
        for name in task_names:
            db.add(
                PipelineTask(
                    photo_id=photo_id,
                    phase=phase,
                    task_name=name,
                    status="pending",
                )
            )
        db.commit()
    finally:
        db.close()


def _update_task(photo_id: int, phase: str, task_name: str, **fields) -> None:
    """Update PipelineTask fields; silently does nothing if the row doesn't exist."""
    db = SessionLocal()
    try:
        task = db.query(PipelineTask).filter_by(photo_id=photo_id, phase=phase, task_name=task_name).first()
        if task is not None:
            for key, value in fields.items():
                setattr(task, key, value)
            db.commit()
    finally:
        db.close()


@asynccontextmanager
async def track_task(photo_id: int, phase: str, task_name: str):
    """
    Async context manager that tracks task status in the main DB.

    On enter  → status='running', started_at=now
    On success → status='done',   finished_at=now
    On error   → status='failed', finished_at=now, error=str(exc); re-raises
    """
    _update_task(photo_id, phase, task_name, status="running", started_at=datetime.now(timezone.utc))
    try:
        yield
        _update_task(photo_id, phase, task_name, status="done", finished_at=datetime.now(timezone.utc))
    except Exception as exc:
        _update_task(
            photo_id, phase, task_name, status="failed", finished_at=datetime.now(timezone.utc), error=str(exc)
        )
        raise


def get_active_pipeline_tasks(db: Session) -> list[PipelineTask]:
    """Return tasks that are pending or running (used for the Processing Page)."""
    return (
        db.query(PipelineTask)
        .filter(PipelineTask.status.in_(["pending", "running"]))
        .order_by(PipelineTask.created_at.desc())
        .all()
    )


def get_photo_pipeline_tasks(db: Session, photo_id: int) -> list[PipelineTask]:
    """Return all pipeline tasks for a specific photo."""
    return db.query(PipelineTask).filter_by(photo_id=photo_id).order_by(PipelineTask.created_at.asc()).all()


def get_recent_pipeline_tasks(db: Session, limit: int = 50) -> list[PipelineTask]:
    """Return the most recently created pipeline tasks."""
    return db.query(PipelineTask).order_by(PipelineTask.created_at.desc()).limit(limit).all()


def recover_interrupted_pipelines(db: Session) -> list[int]:
    """
    Called at startup: find photos with stuck (pending/running) tasks left over
    from a previous crash, delete all their task records, and return the photo_ids
    so the caller can re-run the full pipeline for each one.
    """
    rows = db.query(PipelineTask.photo_id).filter(PipelineTask.status.in_(["pending", "running"])).distinct().all()
    photo_ids = [r[0] for r in rows]
    if not photo_ids:
        return []

    db.query(PipelineTask).filter(PipelineTask.photo_id.in_(photo_ids)).delete(synchronize_session=False)
    db.commit()
    return photo_ids
