# ruff: noqa: F811 -- imported shared pytest fixture
"""Launch endpoints retain outputs and evidence until the scheduler executes."""

import importlib
import sys
from unittest.mock import MagicMock

import pytest

from src import models
from tests.test_pipeline_queue import queue_store  # noqa: F401


@pytest.fixture
def routes(monkeypatch, queue_store):
    # These imports initialize external AI, vector, watcher and queue services;
    # endpoints below still use real database and admission implementations.
    for name in [
        "src.vector_db_services",
        "src.ai.registry",
        "src.ai.translator",
        "src.queues.folder_scan_queue",
        "src.queues.clip_queue",
        "src.queues.vision_queue",
        "src.queues.embedding_queue",
        "src.queues.translation_queue",
        "src.queues.queue_config",
        "src.model_services",
        "src.watcher_service",
        "src.task_notifier",
    ]:
        monkeypatch.setitem(sys.modules, name, MagicMock())
    main = importlib.import_module("src.main")
    _, factory = queue_store
    monkeypatch.setattr(main, "SessionLocal", factory)
    return main


@pytest.mark.asyncio
async def test_manual_rerun_preserves_outputs_and_deduplicates(routes, queue_store, monkeypatch):
    queue, factory = queue_store
    monkeypatch.setattr("threading.Thread", MagicMock())
    with factory() as db:
        db.add(models.Tag(id=1, name="keep"))
        db.add(models.PhotoTag(photo_id=1, tag_id=1))
        db.commit()
        first = await routes.run_pipeline_for_photo_endpoint(1, None, db)
        second = await routes.run_pipeline_for_photo_endpoint(1, None, db)
        assert db.query(models.PhotoTag).count() == 1
        assert db.query(models.PipelineRun).count() == 1
        assert first["run_id"] == second["run_id"]


@pytest.mark.asyncio
async def test_retry_endpoint_preserves_failed_attempt(routes, queue_store, monkeypatch):
    queue, factory = queue_store
    monkeypatch.setattr("threading.Thread", MagicMock())
    with factory() as db:
        old = models.PipelineRun(photo_id=1, source="manual", status="completed-with-errors")
        db.add(old)
        db.flush()
        failed = models.PipelineTask(
            photo_id=1, run_id=old.id, phase="phase_1", task_name="vision_task", status="failed", error="original"
        )
        db.add(failed)
        db.commit()
        result = await routes.retry_pipeline_task_endpoint(failed.id, db)
        db.refresh(failed)
        assert (failed.status, failed.error) == ("failed", "original")
        assert result["run_id"] != old.id
        assert db.get(models.PipelineQueueEntry, result["run_id"]).retry_task_name == "vision_task"


def test_agent_rerun_uses_shared_admission_without_clearing(routes, queue_store, monkeypatch):
    queue, factory = queue_store
    tools = importlib.import_module("src.graphs.tools")
    monkeypatch.setattr(tools, "SessionLocal", factory)
    monkeypatch.setattr("threading.Thread", MagicMock())
    with factory() as db:
        db.add(models.Tag(id=1, name="keep"))
        db.add(models.PhotoTag(photo_id=1, tag_id=1))
        db.commit()
    result = tools.rerun_pipeline_for_photos.invoke({"photo_ids": [1, 2]})
    tools.rerun_pipeline_for_photos.invoke({"photo_ids": [1]})
    with factory() as db:
        assert db.query(models.PhotoTag).count() == 1
        assert [
            (r.photo_id, r.source, r.status) for r in db.query(models.PipelineRun).order_by(models.PipelineRun.id)
        ] == [(1, "agent", "queued"), (2, "agent", "queued")]
    assert "queued" in result.lower()


@pytest.mark.asyncio
async def test_startup_migrates_and_recovers_before_watchers(routes, queue_store, monkeypatch):
    queue, factory = queue_store
    from src.db import database

    old = queue.enqueue_photo_run(1, "watcher")
    models.PipelineQueueEntry.__table__.drop(factory.kw["bind"])
    monkeypatch.setattr(database, "engine", factory.kw["bind"])
    monkeypatch.setattr(routes, "_eager_load_chat_model", lambda: None)
    observed = []

    def start_watchers(db):
        with factory() as reader:
            observed.append(reader.get(models.PipelineRun, old).status)
        assert observed == ["interrupted"], "startup must recover before enabling watcher events"
        queue.enqueue_photo_run(2, "watcher")

    monkeypatch.setattr(routes.watcher_service, "start_all", start_watchers)
    lifetime = routes.lifespan(routes.app)
    try:
        await anext(lifetime)
        assert observed == ["interrupted"]
        with factory() as db:
            assert db.query(models.PipelineRun).filter_by(photo_id=2).one().status == "queued"
    finally:
        await lifetime.aclose()
