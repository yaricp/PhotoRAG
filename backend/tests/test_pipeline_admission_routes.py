# ruff: noqa: F811 -- imported shared pytest fixture
"""Launch endpoints retain outputs and evidence until the scheduler executes."""

import importlib
import sys
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

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


def test_queue_status_endpoint_exposes_position_and_wait_time(routes, queue_store):
    queue, _ = queue_store
    first = queue.enqueue_photo_run(1, "watcher")
    second = queue.enqueue_photo_run(2, "manual")
    client = TestClient(routes.app)

    response = client.get(f"/api/pipeline/runs/{second}/queue")
    assert response.status_code == 200
    assert response.json()["run_id"] == second
    assert response.json()["position"] == 2
    assert response.json()["wait_seconds"] >= 0

    queue.claim_next_run()
    assert client.get(f"/api/pipeline/runs/{second}/queue").json()["position"] == 1
    assert client.get(f"/api/pipeline/runs/{first}/queue").json()["position"] is None
    assert client.get("/api/pipeline/runs/99999/queue").status_code == 404


def test_resume_endpoint_requeues_only_the_selected_interrupted_run(routes, queue_store):
    queue, factory = queue_store
    with factory() as db:
        old = models.PipelineRun(photo_id=1, source="watcher", status="interrupted")
        other = models.PipelineRun(photo_id=2, source="scanner", status="interrupted")
        db.add_all([old, other])
        db.flush()
        db.add(models.PipelineQueueEntry(run_id=old.id, lane="local-ollama", retry_task_name="vision_task"))
        original_task = models.PipelineTask(
            photo_id=1, run_id=old.id, phase="phase_1", task_name="vision_task", status="interrupted", error="runner stopped"
        )
        db.add(original_task)
        db.flush()
        old_id, other_id, task_id = old.id, other.id, original_task.id
        db.commit()

    client = TestClient(routes.app)
    response = client.post(f"/api/pipeline/runs/{old_id}/resume")
    assert response.status_code == 200
    resumed_id = response.json()["run_id"]
    assert response.json()["resumed_from_run_id"] == old_id
    with factory() as db:
        assert db.get(models.PipelineRun, old_id).status == "interrupted"
        assert db.get(models.PipelineRun, other_id).status == "interrupted"
        assert (db.get(models.PipelineTask, task_id).status, db.get(models.PipelineTask, task_id).error) == (
            "interrupted", "runner stopped"
        )
        resumed = db.get(models.PipelineRun, resumed_id)
        assert (resumed.photo_id, resumed.status, resumed.source) == (1, "queued", "resume")
        assert db.get(models.PipelineQueueEntry, resumed_id).retry_task_name == "vision_task"

    assert client.post("/api/pipeline/runs/99999/resume").status_code == 404
    running_id = queue.enqueue_photo_run(3, "manual")
    assert client.post(f"/api/pipeline/runs/{running_id}/resume").status_code == 409


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
    owner = queue.initialize_queue(factory.kw["bind"])
    owner.close()


def test_model_save_conflicts_with_running_photo_without_mutation(routes, queue_store):
    from fastapi import HTTPException

    from src.schemas import AIModelConfigUpdate

    queue, factory = queue_store
    queue.enqueue_photo_run(1, "manual")
    queue.claim_next_run()
    with factory() as db:
        with pytest.raises(HTTPException) as conflict:
            routes.update_model_endpoint(
                "vision",
                AIModelConfigUpdate(
                    mode="remote", model_provider="openai", model_name="test", url="https://api.openai.com"
                ),
                db,
            )
        assert conflict.value.status_code == 409
        db.expire_all()
        assert db.query(models.AIModelConfig).one().model_provider == "ollama"


@pytest.mark.asyncio
async def test_startup_failure_releases_lifecycle_owner(routes, queue_store, monkeypatch):
    from src.db import database

    queue, factory = queue_store
    monkeypatch.setattr(database, "engine", factory.kw["bind"])

    def fail_start(db):
        raise RuntimeError("watcher startup failed")

    monkeypatch.setattr(routes.watcher_service, "start_all", fail_start)
    lifetime = routes.lifespan(routes.app)
    with pytest.raises(RuntimeError, match="watcher startup failed"):
        await anext(lifetime)
    owner = queue.initialize_queue(factory.kw["bind"])
    owner.close()


@pytest.fixture
def embedding_store(routes, queue_store, monkeypatch):
    import sqlite_vec
    from sqlalchemy import event, text

    queue, factory = queue_store
    engine = factory.kw["bind"]

    def load_vectors(connection, _):
        connection.enable_load_extension(True)
        sqlite_vec.load(connection)
        connection.enable_load_extension(False)

    event.listen(engine, "connect", load_vectors)
    engine.dispose()
    monkeypatch.delitem(sys.modules, "src.vector_db_services")
    vectors = importlib.import_module("src.vector_db_services")
    with factory() as db:
        db.add(models.AIModelConfig(type="embedding", mode="remote", model_provider="openai", model_name="old-model"))
        db.add(models.PhotoEmbedding(id=1, photo_id=1, model="old-model"))
        db.execute(text("CREATE VIRTUAL TABLE photo_embeddings_vss USING vec0(embedding FLOAT[3])"))
        db.execute(text("INSERT INTO photo_embeddings_vss(rowid, embedding) VALUES (1, '[1,2,3]')"))
        db.commit()
    return vectors


def test_embedding_transition_blocks_claim_until_config_and_storage_match(
    routes, queue_store, embedding_store, monkeypatch
):
    import threading
    from concurrent.futures import ThreadPoolExecutor, TimeoutError

    from src.schemas import AIModelConfigUpdate

    queue, factory = queue_store
    vectors = embedding_store
    run_id = queue.enqueue_photo_run(1, "manual")
    original_rebuild = vectors.rebuild_embeddings_vss
    started = threading.Event()
    claims = []

    def claim():
        started.set()
        run = queue.claim_next_run()
        with factory() as db:
            return (
                run.id,
                db.query(models.AIModelConfig).filter_by(type="embedding").one().model_name,
                vectors.current_vss_dimension(db),
                db.query(models.PhotoEmbedding).count(),
            )

    with ThreadPoolExecutor(max_workers=1) as workers:

        def rebuild(db, dimension, **kwargs):
            claims.append(workers.submit(claim))
            assert started.wait(2)
            with pytest.raises(TimeoutError):
                claims[0].result(timeout=0.1)
            original_rebuild(db, dimension, **kwargs)

        monkeypatch.setattr(vectors, "rebuild_embeddings_vss", rebuild)
        with factory() as db:
            routes.update_model_endpoint(
                "embedding", AIModelConfigUpdate(mode="remote", model_provider="openai", model_name="bge-small"), db
            )
        assert claims[0].result(timeout=3) == (run_id, "bge-small", 512, 0)


def test_embedding_rebuild_failure_rolls_back_config_vectors_and_map(routes, queue_store, embedding_store, monkeypatch):
    from sqlalchemy import text

    from src.schemas import AIModelConfigUpdate

    _, factory = queue_store
    vectors = embedding_store
    original_rebuild = vectors.rebuild_embeddings_vss

    def fail_after_rebuild(db, dimension, **kwargs):
        original_rebuild(db, dimension, **kwargs)
        raise RuntimeError("rebuild interrupted")

    monkeypatch.setattr(vectors, "rebuild_embeddings_vss", fail_after_rebuild)
    with factory() as db:
        with pytest.raises(RuntimeError, match="rebuild interrupted"):
            routes.update_model_endpoint(
                "embedding", AIModelConfigUpdate(mode="remote", model_provider="openai", model_name="bge-small"), db
            )
    with factory() as db:
        assert db.query(models.AIModelConfig).filter_by(type="embedding").one().model_name == "old-model"
        assert vectors.current_vss_dimension(db) == 3
        assert db.query(models.PhotoEmbedding).one().model == "old-model"
        assert db.execute(text("SELECT rowid FROM photo_embeddings_vss")).scalars().all() == [1]


def test_standalone_vector_rebuild_still_commits(queue_store, embedding_store):
    _, factory = queue_store
    vectors = embedding_store
    with factory() as db:
        assert vectors.current_vss_dimension(db) == 3
        vectors.rebuild_embeddings_vss(db, 512)
    with factory() as db:
        assert vectors.current_vss_dimension(db) == 512
        assert db.query(models.PhotoEmbedding).count() == 0


def test_standalone_vector_ddl_failure_restores_old_storage(queue_store, embedding_store):
    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError

    _, factory = queue_store
    vectors = embedding_store
    with factory() as db:
        with pytest.raises(OperationalError):
            vectors.rebuild_embeddings_vss(db, 0)
    with factory() as db:
        assert vectors.current_vss_dimension(db) == 3
        assert db.query(models.PhotoEmbedding).count() == 1
        assert db.execute(text("SELECT rowid FROM photo_embeddings_vss")).scalars().all() == [1]
