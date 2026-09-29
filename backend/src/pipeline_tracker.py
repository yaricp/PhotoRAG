"""Persistent run and task-attempt tracking for photo processing."""

from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.db.database import SessionLocal
from src.models import PipelineRun, PipelineTask

_current_run = ContextVar("pipeline_run_id", default=None)


@contextmanager
def pipeline_run_context(run_id: int):
    """Bind child asyncio tasks and asyncio.to_thread calls to one run."""
    token = _current_run.set(run_id)
    try:
        yield
    finally:
        _current_run.reset(token)


def create_pipeline_run(photo_id: int, source: str) -> int:
    with SessionLocal() as db:
        run = PipelineRun(photo_id=photo_id, source=source, status="queued")
        db.add(run)
        db.commit()
        return run.id


def _run_id(db, photo_id, run_id=None):
    selected = run_id if run_id is not None else _current_run.get()
    if selected is not None:
        run = db.get(PipelineRun, selected)
        if run is None or run.photo_id != photo_id:
            raise ValueError("Pipeline run does not belong to this photo")
        return selected
    run = db.query(PipelineRun).filter_by(photo_id=photo_id).order_by(PipelineRun.id.desc()).first()
    return run.id if run else None


def init_pipeline_tasks(photo_id: int, phase: str, task_names: list[str], *, run_id=None) -> None:
    """Append attempts, retaining all existing evidence. Prefer an explicit run context."""
    if not task_names:
        return
    with SessionLocal() as db:
        selected = _run_id(db, photo_id, run_id)
        if selected is None:
            run = PipelineRun(photo_id=photo_id, source="legacy", status="running")
            db.add(run)
            db.flush()
            selected = run.id
        for name in task_names:
            previous = (
                db.query(PipelineTask)
                .filter_by(run_id=selected, phase=phase, task_name=name)
                .order_by(PipelineTask.id.desc())
                .first()
            )
            db.add(
                PipelineTask(
                    photo_id=photo_id,
                    run_id=selected,
                    phase=phase,
                    task_name=name,
                    attempt=(previous.attempt + 1 if previous else 1),
                    status="pending",
                )
            )
        db.commit()


def _task_id(photo_id, phase, task_name, run_id=None):
    with SessionLocal() as db:
        selected = _run_id(db, photo_id, run_id)
        query = db.query(PipelineTask).filter_by(photo_id=photo_id, phase=phase, task_name=task_name)
        query = query.filter_by(run_id=selected)
        task = query.order_by(PipelineTask.id.desc()).first()
        return task.id if task else None


def _update_task_id(task_id, **fields):
    if task_id is None:
        return
    with SessionLocal() as db:
        task = db.get(PipelineTask, task_id)
        if task is not None:
            for key, value in fields.items():
                setattr(task, key, value)
            db.commit()


def finalize_pipeline_run(run_id: int) -> str:
    with SessionLocal() as db:
        run = db.get(PipelineRun, run_id)
        if run is None:
            raise ValueError("Unknown pipeline run")
        tasks = db.query(PipelineTask).filter_by(run_id=run_id).order_by(PipelineTask.id).all()
        latest = {(t.phase, t.task_name): t for t in tasks}
        errors = [t for t in latest.values() if t.status != "done" and not (t.status == "skipped" and not t.required)]
        run.status = "completed-with-errors" if errors or not tasks else "completed"
        run.finished_at = datetime.now(timezone.utc)
        run.summary = "; ".join(f"{t.task_name}: {t.error or t.skip_reason or t.status}" for t in errors)[:2000]
        db.commit()
        return run.status


def mark_task_skipped(photo_id: int, phase: str, task_name: str, reason: str, *, run_id=None, required=True):
    """Missing prerequisites remain required; legitimate inapplicability sets required=False."""
    _update_task_id(
        _task_id(photo_id, phase, task_name, run_id),
        status="skipped",
        skip_reason=reason[:2000],
        required=required,
        finished_at=datetime.now(timezone.utc),
    )


def get_task_outcome(photo_id: int, phase: str, task_name: str):
    task_id = _task_id(photo_id, phase, task_name)
    with SessionLocal() as db:
        task = db.get(PipelineTask, task_id) if task_id is not None else None
        return (task.status, task.required) if task else (None, True)


@asynccontextmanager
async def track_task(photo_id: int, phase: str, task_name: str):
    task_id = _task_id(photo_id, phase, task_name)
    _update_task_id(task_id, status="running", started_at=datetime.now(timezone.utc))
    try:
        yield
        with SessionLocal() as db:
            task = db.get(PipelineTask, task_id) if task_id is not None else None
            skipped = task is not None and task.status == "skipped"
        if not skipped:
            _update_task_id(task_id, status="done", finished_at=datetime.now(timezone.utc))
    except Exception as exc:
        _update_task_id(task_id, status="failed", finished_at=datetime.now(timezone.utc), error=str(exc)[:2000])
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
    """Preserve unfinished runs and task evidence; callers must not replay them."""
    runs = db.query(PipelineRun).filter(PipelineRun.status.in_(["queued", "running"])).all()
    photo_ids = sorted({run.photo_id for run in runs})
    for run in runs:
        run.status = "interrupted"
        run.finished_at = datetime.utcnow()
    db.query(PipelineTask).filter(PipelineTask.status.in_(["pending", "running"])).update(
        {PipelineTask.status: "interrupted"}, synchronize_session=False
    )
    db.commit()
    return photo_ids
