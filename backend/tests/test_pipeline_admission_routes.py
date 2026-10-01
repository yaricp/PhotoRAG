# ruff: noqa: F811 -- imported shared pytest fixture
"""Launch endpoints retain outputs and evidence until the scheduler executes."""

import importlib
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
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
        assert db.get(models.PipelineQueueEntry, result["run_id"]).retry_task_names == (
            '["vision_task", "final_embedding_task", "translate_description_task"]'
        )


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


def test_watchers_api_includes_updated_at_as_utc(routes, queue_store, monkeypatch):
    _, factory = queue_store
    updated_at = datetime(2026, 9, 30, 18, 42, 15)
    with factory() as db:
        watcher = models.Watcher(
            path="/photos/inbox",
            destination_path="/photos/organized",
            status="active",
            updated_at=updated_at,
        )
        db.add(watcher)
        db.commit()
        watcher_id = watcher.id

    from src import deps

    monkeypatch.setattr(deps, "SessionLocal", factory)
    response = TestClient(routes.app).get("/api/watchers/")

    assert response.status_code == 200
    watcher = next(item for item in response.json() if item["id"] == watcher_id)
    assert watcher["updated_at"] == "2026-09-30T18:42:15+00:00"

    created_watcher = SimpleNamespace(
        id=12,
        path="/photos/new-inbox",
        destination_path="/photos/new-organized",
        status="active",
        updated_at=datetime(2026, 9, 30, 19, 42, 15, tzinfo=timezone(timedelta(hours=3))),
    )
    monkeypatch.setattr(routes.watcher_service, "start_watcher", lambda *_args: created_watcher)
    created = TestClient(routes.app).post(
        "/api/watchers/",
        json={"path": created_watcher.path, "destination_path": created_watcher.destination_path},
    )
    assert created.status_code == 200
    assert created.json()["updated_at"] == "2026-09-30T16:42:15+00:00"


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


def test_paginated_run_history_includes_photo_outputs_and_task_errors(routes, queue_store, monkeypatch):
    queue, factory = queue_store
    with factory() as db:
        first_photo = db.get(models.Photo, 1)
        first_photo.description = "A mountain at sunrise"
        first_photo.translated_description = "Гора на рассвете"
        first_photo.ocr_text = "Trail marker"
        second_photo = db.get(models.Photo, 2)
        second_photo.description = "A red bicycle"
        db.add_all([models.Tag(id=1, name="mountain"), models.Category(id=1, name="landscape")])
        db.add(models.PhotoTag(photo_id=1, tag_id=1, confidence_score=0.91))
        db.add(models.PhotoCategory(photo_id=1, category_id=1, confidence_score=0.87))
        first = models.PipelineRun(
            photo_id=1,
            source="watcher",
            status="completed-with-errors",
            created_at=datetime(2026, 1, 1),
            summary="vision_task: runner stopped",
        )
        second = models.PipelineRun(
            photo_id=2,
            source="manual",
            status="completed",
            created_at=datetime(2026, 1, 2),
        )
        db.add_all([first, second])
        db.flush()
        db.add_all(
            [
                models.PipelineTask(
                    photo_id=1,
                    run_id=first.id,
                    attempt=2,
                    phase="phase_1",
                    task_name="vision_task",
                    status="failed",
                    error="runner stopped",
                ),
                models.PipelineTask(
                    photo_id=1,
                    run_id=first.id,
                    attempt=2,
                    phase="phase_1",
                    task_name="ocr_task",
                    status="done",
                ),
            ]
        )
        first_id, second_id = first.id, second.id
        db.commit()

    from src import deps

    monkeypatch.setattr(deps, "SessionLocal", factory)
    client = TestClient(routes.app)
    page_one = client.get("/api/pipeline/runs?bucket=completed&page=1&size=1")
    assert page_one.status_code == 200
    assert (page_one.json()["total"], page_one.json()["page"], page_one.json()["pages"]) == (2, 1, 2)
    assert page_one.json()["items"][0]["run_id"] == second_id
    assert page_one.json()["items"][0]["photo"]["description"] == "A red bicycle"

    page_two = client.get("/api/pipeline/runs?bucket=completed&page=2&size=1").json()
    run = page_two["items"][0]
    assert run["run_id"] == first_id
    assert run["status"] == "completed-with-errors"
    assert run["summary"] == "vision_task: runner stopped"
    assert run["photo"] == {
        "id": 1,
        "file_path": "/1.jpg",
        "description": "A mountain at sunrise",
        "translated_description": "Гора на рассвете",
        "ocr_text": "Trail marker",
        "tags": ["mountain"],
        "categories": ["landscape"],
    }
    assert [(task["task_name"], task["status"], task["error"], task["attempt"]) for task in run["tasks"]] == [
        ("vision_task", "failed", "runner stopped", 2),
        ("ocr_task", "done", None, 2),
    ]

    active_id = queue.enqueue_photo_run(3, "watcher")
    active_page = client.get("/api/pipeline/runs?bucket=active&page=1&size=20").json()
    assert [item["run_id"] for item in active_page["items"]] == [active_id]
    assert active_page["items"][0]["queue_position"] == 1
    assert active_page["items"][0]["wait_seconds"] >= 0
    assert client.get("/api/pipeline/runs?bucket=other").status_code == 422


def test_run_history_groups_attempts_by_photo_and_active_retry_supersedes_completed(routes, queue_store, monkeypatch):
    _, factory = queue_store
    with factory() as db:
        photo = db.get(models.Photo, 1)
        photo.description = "Preserved from a completed attempt"
        completed = models.PipelineRun(
            photo_id=photo.id,
            source="watcher",
            status="completed",
            created_at=datetime(2026, 1, 1),
        )
        failed = models.PipelineRun(
            photo_id=photo.id,
            source="retry",
            status="completed-with-errors",
            created_at=datetime(2026, 1, 2),
            summary="tag task failed",
        )
        active_retry = models.PipelineRun(
            photo_id=photo.id,
            source="retry",
            status="queued",
            created_at=datetime(2026, 1, 3),
        )
        running = models.PipelineRun(
            photo_id=2,
            source="watcher",
            status="running",
            created_at=datetime(2026, 1, 4),
            started_at=datetime(2026, 1, 4),
        )
        later_queued = models.PipelineRun(
            photo_id=3,
            source="scanner",
            status="queued",
            created_at=datetime(2026, 1, 5),
        )
        db.add_all([completed, failed, active_retry, running, later_queued])
        db.flush()
        db.add_all(
            [
                models.PipelineQueueEntry(run_id=active_retry.id, lane="local-ollama", retry_task_name="auto_tag_clip_task"),
                models.PipelineQueueEntry(run_id=running.id, lane="local-ollama"),
                models.PipelineQueueEntry(run_id=later_queued.id, lane="local-ollama"),
                models.PipelineTask(
                    photo_id=photo.id,
                    run_id=completed.id,
                    phase="phase_1",
                    task_name="vision_task",
                    status="done",
                ),
                models.PipelineTask(
                    photo_id=photo.id,
                    run_id=failed.id,
                    phase="phase_1",
                    task_name="auto_tag_clip_task",
                    status="failed",
                    error="tag save failed",
                ),
            ]
        )
        run_ids = [completed.id, failed.id, active_retry.id]
        expected_active_order = [running.id, active_retry.id, later_queued.id]
        db.commit()

    from src import deps

    monkeypatch.setattr(deps, "SessionLocal", factory)
    client = TestClient(routes.app)
    active = client.get("/api/pipeline/runs?bucket=active&page=1&size=10").json()
    assert active["total"] == 3
    assert active["active_total"] == 3
    assert active["completed_total"] == 0
    assert [item["run_id"] for item in active["items"]] == expected_active_order
    card = next(item for item in active["items"] if item["photo_id"] == 1)
    assert card["photo_id"] == 1
    assert card["run_id"] == run_ids[-1]
    assert card["attempt_count"] == 3
    assert [attempt["run_id"] for attempt in card["attempts"]] == run_ids
    assert [attempt["status"] for attempt in card["attempts"]] == [
        "completed",
        "completed-with-errors",
        "queued",
    ]
    completed_page = client.get("/api/pipeline/runs?bucket=completed&page=1&size=1").json()
    assert completed_page["total"] == 0
    assert completed_page["items"] == []


def test_bulk_retry_admits_only_latest_eligible_tasks_and_preserves_outputs(routes, queue_store, monkeypatch):
    _, factory = queue_store
    with factory() as db:
        photo = db.get(models.Photo, 1)
        photo.description = "Keep this successful output"
        failed_run = models.PipelineRun(photo_id=1, source="manual", status="completed-with-errors")
        active_run = models.PipelineRun(photo_id=2, source="retry", status="queued")
        db.add_all([failed_run, active_run])
        db.flush()
        db.add_all(
            [
                models.PipelineTask(
                    photo_id=1,
                    run_id=failed_run.id,
                    phase="phase_1",
                    task_name="vision_task",
                    status="failed",
                    error="model error",
                ),
                models.PipelineTask(
                    photo_id=1,
                    run_id=failed_run.id,
                    phase="phase_2",
                    task_name="translate_description_task",
                    status="skipped",
                    skip_reason="Prerequisite vision_task: failed",
                ),
                models.PipelineTask(
                    photo_id=2,
                    run_id=active_run.id,
                    phase="phase_1",
                    task_name="auto_tag_clip_task",
                    status="failed",
                ),
                models.PipelineQueueEntry(run_id=active_run.id, lane="local-ollama"),
            ]
        )
        db.commit()

    client = TestClient(routes.app)
    eligibility = client.get("/api/pipeline/retry-eligible/count")
    assert eligibility.status_code == 200
    assert eligibility.json() == {"eligible_photos": 1, "eligible_tasks": 2}
    response = client.post("/api/pipeline/retry-eligible")
    assert response.status_code == 202
    assert response.json() == {"status": "queued", "queued_photos": 1, "queued_tasks": 2, "run_ids": [3]}
    with factory() as db:
        retry_run = db.get(models.PipelineRun, response.json()["run_ids"][0])
        entry = db.get(models.PipelineQueueEntry, retry_run.id)
        assert retry_run.photo_id == 1
        assert retry_run.source == "bulk-retry"
        assert entry.retry_task_names == '["vision_task", "translate_description_task"]'
        assert db.get(models.Photo, 1).description == "Keep this successful output"

    from src import deps

    monkeypatch.setattr(deps, "SessionLocal", factory)
    active = client.get("/api/pipeline/runs?bucket=active&page=1&size=10").json()
    retry_card = next(item for item in active["items"] if item["photo_id"] == 1)
    assert retry_card["is_task_retry"] is True
    assert retry_card["retry_tasks"] == [
        {"task_name": "vision_task", "phase": "phase_1"},
        {"task_name": "translate_description_task", "phase": "phase_2"},
    ]

    repeated = client.post("/api/pipeline/retry-eligible")
    assert repeated.status_code == 202
    assert repeated.json()["queued_photos"] == 0
    assert client.get("/api/pipeline/retry-eligible/count").json() == {"eligible_photos": 0, "eligible_tasks": 0}


@pytest.mark.asyncio
async def test_long_completed_run_remains_visible_after_full_rerun(routes, queue_store, monkeypatch):
    queue, factory = queue_store
    with factory() as db:
        old = models.PipelineRun(
            photo_id=4,
            source="watcher",
            status="completed-with-errors",
            summary="task_0: original failure",
        )
        db.add(old)
        db.flush()
        old_id = old.id
        db.add_all(
            [
                models.PipelineTask(
                    photo_id=4,
                    run_id=old_id,
                    attempt=1,
                    phase=f"phase_{index // 10}",
                    task_name=f"task_{index}_task",
                    status="failed" if index == 0 else "done",
                    error="original failure" if index == 0 else None,
                )
                for index in range(55)
            ]
        )
        db.commit()
        result = await routes.run_pipeline_for_photo_endpoint(4, None, db)

    assert result["run_id"] != old_id
    from src import deps

    monkeypatch.setattr(deps, "SessionLocal", factory)
    client = TestClient(routes.app)
    history = client.get("/api/pipeline/runs?bucket=active&page=1&size=20").json()
    assert history["total"] == 1
    run = history["items"][0]
    assert run["run_id"] == result["run_id"]
    assert run["attempt_count"] == 2
    assert run["attempts"][0]["run_id"] == old_id
    assert len(run["attempts"][0]["tasks"]) == 55
    assert (run["attempts"][0]["tasks"][0]["status"], run["attempts"][0]["tasks"][0]["error"]) == (
        "failed",
        "original failure",
    )

    completed = client.get("/api/pipeline/runs?bucket=completed&page=1&size=20").json()
    assert completed["total"] == 0
    with factory() as db:
        assert db.get(models.PipelineRun, old_id).status == "completed-with-errors"
        assert db.query(models.PipelineTask).filter_by(run_id=old_id).count() == 55


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


@pytest.mark.asyncio
async def test_startup_retry_preference_enqueues_incomplete_tasks_before_watchers(routes, queue_store, monkeypatch):
    queue, factory = queue_store
    from src.db import database
    from src.db_service import set_setting

    old = queue.enqueue_photo_run(1, "watcher")
    with factory() as db:
        db.add(
            models.PipelineTask(
                photo_id=1,
                run_id=old,
                phase="phase_1",
                task_name="vision_task",
                status="interrupted",
                error="application closed",
            )
        )
        set_setting(db, "retry_unfinished_at_startup", "true")

    monkeypatch.setattr(database, "engine", factory.kw["bind"])
    monkeypatch.setattr(routes, "_eager_load_chat_model", lambda: None)
    observed = []

    def start_watchers(db):
        with factory() as reader:
            old_run = reader.get(models.PipelineRun, old)
            queued = reader.query(models.PipelineRun).filter_by(photo_id=1, status="queued").one()
            entry = reader.get(models.PipelineQueueEntry, queued.id)
            observed.extend([old_run.status, entry.retry_task_names])

    monkeypatch.setattr(routes.watcher_service, "start_all", start_watchers)
    lifetime = routes.lifespan(routes.app)
    try:
        await anext(lifetime)
        assert observed == ["interrupted", '["vision_task"]']
    finally:
        await lifetime.aclose()


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


def test_model_save_remains_available_while_photo_is_queued(routes, queue_store, monkeypatch):
    from src.schemas import AIModelConfigUpdate

    queue, factory = queue_store
    queued_run_id = queue.enqueue_photo_run(2, "manual")
    monkeypatch.setattr("src.ollama_policy.validate_configuration", lambda *_args: None)

    with factory() as db:
        saved = routes.update_model_endpoint(
            "vision",
            AIModelConfigUpdate(
                mode="remote",
                model_provider="ollama",
                model_name="qwen3-vl:2b-instruct",
                url="http://localhost:11434",
            ),
            db,
        )
        assert (saved.mode, saved.model_provider, saved.model_name) == (
            "remote", "ollama", "qwen3-vl:2b-instruct"
        )
        assert db.get(models.PipelineRun, queued_run_id).status == "queued"


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
