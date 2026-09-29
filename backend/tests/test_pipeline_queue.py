"""Persistent admission must survive separate connections and concurrent producers."""

import importlib.util
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src import models


@pytest.fixture
def queue_store(tmp_path, monkeypatch):
    if not importlib.util.find_spec("src.pipeline_queue"):
        yield None
        return
    from src import pipeline_queue as queue

    engine = create_engine(f"sqlite:///{tmp_path / 'queue.db'}", connect_args={"timeout": 30})
    models.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(queue, "SessionLocal", factory)
    with factory() as db:
        db.add_all([models.Photo(id=i, file_path=f"/{i}.jpg", hash=str(i)) for i in range(1, 30)])
        db.add(
            models.AIModelConfig(type="vision", mode="remote", model_provider="ollama", url="http://localhost:11434")
        )
        db.commit()
    yield queue, factory
    engine.dispose()


def test_concurrent_producers_deduplicate_and_claim_in_order(queue_store):
    assert queue_store is not None, "shared admission queue is missing"
    queue, factory = queue_store
    with ThreadPoolExecutor(max_workers=8) as workers:
        futures = [
            workers.submit(queue.enqueue_photo_run, i, source)
            for source in ["watcher", "scanner", "manual"]
            for i in range(1, 25)
        ]
        ids = [f.result() for f in futures]
    assert len(set(ids)) == 24
    with factory() as db:
        runs = db.query(models.PipelineRun).order_by(models.PipelineRun.id).all()
        expected = [r.id for r in runs]
        assert len(runs) == 24
    claimed = []
    for _ in range(24):
        with ThreadPoolExecutor(max_workers=4) as workers:
            results = list(workers.map(lambda _: queue.claim_next_run(), range(4)))
        active = [r for r in results if r is not None]
        assert len(active) == 1
        claimed.append(active[0].id)
        with factory() as db:
            db.get(models.PipelineRun, active[0].id).status = "completed"
            db.commit()
    assert claimed == expected


def test_restart_preserves_evidence_and_resume_selects_only_one(queue_store):
    queue, factory = queue_store
    from src.pipeline_tracker import recover_interrupted_pipelines

    first = queue.enqueue_photo_run(1, "watcher")
    second = queue.enqueue_photo_run(2, "scanner", 7)
    queue.claim_next_run()
    with factory() as db:
        db.add_all(
            [
                models.PipelineTask(
                    run_id=first,
                    photo_id=1,
                    phase="phase_1",
                    task_name="vision_task",
                    status="failed",
                    error="original failure",
                ),
                models.PipelineTask(
                    run_id=first, photo_id=1, phase="phase_2", task_name="translation", status="pending"
                ),
            ]
        )
        db.commit()
        recover_interrupted_pipelines(db)
    with factory() as db:
        assert [r.status for r in db.query(models.PipelineRun).order_by(models.PipelineRun.id)] == [
            "interrupted",
            "interrupted",
        ]
        assert [(t.status, t.error) for t in db.query(models.PipelineTask).order_by(models.PipelineTask.id)] == [
            ("failed", "original failure"),
            ("interrupted", None),
        ]
    assert queue.claim_next_run() is None
    resumed = queue.resume_run(second)
    assert resumed not in (first, second)
    assert queue.claim_next_run().id == resumed
    assert queue.claim_next_run() is None
    with factory() as db:
        assert db.get(models.PipelineRun, first).status == "interrupted"
        assert db.get(models.PipelineRun, second).status == "interrupted"
        assert db.get(models.PipelineQueueEntry, resumed).folder_scanner_id == 7


@pytest.mark.parametrize(
    "provider,url", [("openai", "https://api.openai.com"), ("ollama", "http://other-host:11434"), (None, None)]
)
def test_local_lane_does_not_block_unrelated_models(queue_store, provider, url):
    queue, factory = queue_store
    local = queue.enqueue_photo_run(1, "watcher")
    blocked = queue.enqueue_photo_run(2, "watcher")
    assert queue.claim_next_run().id == local
    with factory() as db:
        config = db.query(models.AIModelConfig).one()
        config.mode = "remote" if provider else "local"
        config.model_provider = provider
        config.url = url
        db.commit()
    other = queue.enqueue_photo_run(3, "manual")
    assert queue.claim_next_run().id == other
    assert queue.claim_next_run() is None
    assert blocked != other


@pytest.mark.asyncio
async def test_accepted_execution_defers_clear_and_keeps_duplicate_outputs(queue_store, monkeypatch):
    queue, factory = queue_store
    import sys
    from types import SimpleNamespace

    with factory() as db:
        db.add(models.Tag(id=1, name="keep"))
        db.add(models.PhotoTag(photo_id=1, tag_id=1))
        db.commit()
    first = queue.enqueue_photo_run(1, "manual", clear_outputs=True)
    duplicate = queue.enqueue_photo_run(1, "agent", clear_outputs=True)
    assert duplicate == first
    with factory() as db:
        assert db.query(models.PhotoTag).filter_by(photo_id=1).count() == 1
    observed = []

    async def execute(photo_id, folder_scanner_id, *, run_id):
        with factory() as db:
            observed.append((photo_id, run_id, db.query(models.PhotoTag).count()))
            db.get(models.PipelineRun, run_id).status = "completed"
            db.commit()

    monkeypatch.setitem(sys.modules, "src.incoming_pipeline", SimpleNamespace(start_pipeline=execute))
    assert hasattr(queue, "execute_claimed_run"), "scheduler execution is missing"
    await queue.execute_claimed_run(queue.claim_next_run())
    assert observed == [(1, first, 0)]
    with factory() as db:
        assert db.get(models.PipelineRun, first).status == "completed"


@pytest.mark.asyncio
async def test_failed_execution_releases_lane_preserves_error_and_retry_intent(queue_store, monkeypatch):
    queue, factory = queue_store
    import sys
    from types import SimpleNamespace

    first = queue.enqueue_photo_run(1, "retry", retry_task_name="vision_task")
    second = queue.enqueue_photo_run(2, "watcher")
    observed = []

    async def fail(photo_id, task_name, *, run_id):
        observed.append((photo_id, task_name, run_id))
        raise RuntimeError("runner unavailable")

    monkeypatch.setitem(sys.modules, "src.incoming_pipeline", SimpleNamespace(retry_pipeline_task=fail))
    assert hasattr(queue, "execute_claimed_run"), "scheduler execution is missing"
    await queue.execute_claimed_run(queue.claim_next_run())
    assert observed == [(1, "vision_task", first)]
    with factory() as db:
        run = db.get(models.PipelineRun, first)
        assert run.status == "completed-with-errors"
        assert "runner unavailable" in run.summary
    assert queue.claim_next_run().id == second


def test_upgrade_initialization_recovers_before_accepting_new_work(queue_store):
    queue, factory = queue_store
    from src.models import PipelineQueueEntry

    old = queue.enqueue_photo_run(1, "watcher")
    PipelineQueueEntry.__table__.drop(factory.kw["bind"])
    assert hasattr(queue, "initialize_queue"), "upgrade initialization is missing"
    queue.initialize_queue(factory.kw["bind"])
    with factory() as db:
        assert db.get(models.PipelineRun, old).status == "interrupted"
    new = queue.enqueue_photo_run(2, "watcher")
    assert queue.claim_next_run().id == new


@pytest.mark.asyncio
async def test_scheduler_drains_new_queue_without_replaying_interrupted(queue_store, monkeypatch):
    import asyncio
    import sys
    from types import SimpleNamespace

    queue, factory = queue_store
    old = queue.enqueue_photo_run(1, "watcher")
    from src.pipeline_tracker import recover_interrupted_pipelines

    with factory() as db:
        recover_interrupted_pipelines(db)
    fresh = queue.enqueue_photo_run(2, "watcher")
    finished = asyncio.Event()

    async def execute(photo_id, folder_scanner_id, *, run_id):
        with factory() as db:
            db.get(models.PipelineRun, run_id).status = "completed"
            db.commit()
        finished.set()

    monkeypatch.setitem(sys.modules, "src.incoming_pipeline", SimpleNamespace(start_pipeline=execute))
    assert hasattr(queue, "run_scheduler"), "scheduler loop is missing"
    scheduler = asyncio.create_task(queue.run_scheduler())
    try:
        await asyncio.wait_for(finished.wait(), timeout=3)
    finally:
        scheduler.cancel()
        await asyncio.gather(scheduler, return_exceptions=True)
    with factory() as db:
        assert db.get(models.PipelineRun, old).status == "interrupted"
        assert db.get(models.PipelineRun, fresh).status == "completed"


def test_queue_positions_and_wait_time(queue_store):
    queue, _ = queue_store
    first = queue.enqueue_photo_run(1, "watcher")
    second = queue.enqueue_photo_run(2, "watcher")
    assert hasattr(queue, "get_queue_details"), "queue visibility is missing"
    assert queue.get_queue_details(first)["position"] == 1
    assert queue.get_queue_details(second)["position"] == 2
    assert queue.get_queue_details(second)["wait_seconds"] >= 0
    queue.claim_next_run()
    assert queue.get_queue_details(first)["position"] is None
    assert queue.get_queue_details(second)["position"] == 1


def test_other_lane_has_shared_capacity(queue_store, monkeypatch):
    from src.config import TaskQueue_Settings

    queue, factory = queue_store
    monkeypatch.setenv("MAX_CONCURRENT_PIPELINES", "2")
    assert TaskQueue_Settings().MAX_CONCURRENT_PIPELINES == 2
    with factory() as db:
        db.query(models.AIModelConfig).delete()
        db.commit()
    for i in range(1, 4):
        queue.enqueue_photo_run(i, "manual")
    assert queue.claim_next_run() is not None
    assert queue.claim_next_run() is not None
    assert queue.claim_next_run() is None


def test_observer_admits_without_executing_on_private_loop(queue_store, monkeypatch, tmp_path):
    queue, factory = queue_store
    from types import SimpleNamespace

    from src import observer

    path = tmp_path / "new.jpg"
    path.write_bytes(b"photo")
    monkeypatch.setattr(observer, "SessionLocal", factory)
    monkeypatch.setattr(observer, "wait_until_file_ready", lambda path: True)
    monkeypatch.setattr(observer, "generate_file_hash", lambda path: "new")
    monkeypatch.setattr(observer, "get_photo_capture_date", lambda path: None)
    monkeypatch.setattr(observer, "move_photo", lambda path, dest: str(path))
    handler = observer.PhotoEventHandler(str(tmp_path))
    handler.on_created(SimpleNamespace(is_directory=False, src_path=str(path)))
    with factory() as db:
        run = db.query(models.PipelineRun).first()
        assert run is not None, "watcher did not persist admitted work"
        assert run.source == "watcher"
        assert run.status == "queued"


@pytest.mark.asyncio
async def test_batch_admits_instead_of_executing(queue_store, monkeypatch):
    queue, factory = queue_store
    from src import incoming_pipeline, pipeline_tracker

    monkeypatch.setattr(pipeline_tracker, "SessionLocal", factory)
    monkeypatch.setattr(incoming_pipeline, "_PHASES", {})
    await incoming_pipeline.run_pipelines_batch([1, 2])
    with factory() as db:
        assert [(r.photo_id, r.status) for r in db.query(models.PipelineRun).order_by(models.PipelineRun.id)] == [
            (1, "queued"),
            (2, "queued"),
        ]


@pytest.mark.parametrize("module_name", ["src.queues.folder_scan_queue", "src.tasks.folder_scanners"])
def test_scanner_variants_admit_registered_photos(queue_store, monkeypatch, tmp_path, module_name):
    import importlib
    import sys
    from types import SimpleNamespace

    queue, factory = queue_store
    scanner = importlib.import_module(module_name)
    monkeypatch.setattr(scanner, "SessionLocal", factory)
    monkeypatch.setattr(scanner, "check_if_file_is_image", lambda path: path.endswith(".jpg"))

    async def old_execution(*args, **kwargs):
        pass

    monkeypatch.setitem(
        sys.modules,
        "src.incoming_pipeline",
        SimpleNamespace(start_pipeline=old_execution, run_pipelines_batch=old_execution),
    )
    folder = tmp_path / "photos"
    folder.mkdir()
    (folder / "scan.jpg").write_bytes(b"scan image")
    assert scanner.start_folder_scanner_task.call_local(str(folder)) is True
    with factory() as db:
        run = db.query(models.PipelineRun).first()
        assert run is not None, "scanner bypassed shared admission"
        assert run.source == "scanner"
        assert run.status == "queued"
        assert db.get(models.PipelineQueueEntry, run.id).folder_scanner_id is not None


def _claim_in_separate_process(database_url):
    from src import pipeline_queue

    engine = create_engine(database_url, connect_args={"timeout": 30})
    pipeline_queue.SessionLocal = sessionmaker(bind=engine)
    try:
        run = pipeline_queue.claim_next_run()
        return run.id if run else None
    finally:
        engine.dispose()


def test_local_claim_limit_is_shared_by_separate_processes(queue_store):
    import multiprocessing
    from concurrent.futures import ProcessPoolExecutor

    queue, factory = queue_store
    first = queue.enqueue_photo_run(1, "watcher")
    queue.enqueue_photo_run(2, "scanner")
    with ProcessPoolExecutor(max_workers=2, mp_context=multiprocessing.get_context("spawn")) as workers:
        results = list(workers.map(_claim_in_separate_process, [str(factory.kw["bind"].url)] * 2))
    assert sorted(value for value in results if value is not None) == [first]
    assert results.count(None) == 1
