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
    assert queue.claim_next_run().id == blocked
    assert queue.claim_next_run().id == other
    assert queue.claim_next_run() is None


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
    owner = queue.initialize_queue(factory.kw["bind"])
    owner.close()
    with factory() as db:
        assert db.get(models.PipelineRun, old).status == "interrupted"
    new = queue.enqueue_photo_run(2, "watcher")
    assert queue.claim_next_run().id == new


def test_collect_retryable_tasks_uses_latest_outcome_and_skips_active_paused_or_canceled(queue_store):
    queue, factory = queue_store
    with factory() as db:
        runs = [
            models.PipelineRun(photo_id=1, source="manual", status="completed-with-errors"),
            models.PipelineRun(photo_id=1, source="retry", status="completed"),
            models.PipelineRun(photo_id=2, source="manual", status="interrupted"),
            models.PipelineRun(photo_id=3, source="manual", status="queued"),
            models.PipelineRun(photo_id=4, source="manual", status="completed-with-errors"),
            models.PipelineRun(photo_id=4, source="retry", status="completed"),
            models.PipelineRun(photo_id=5, source="manual", status="paused"),
            models.PipelineRun(photo_id=6, source="manual", status="completed-with-errors"),
        ]
        db.add_all(runs)
        db.flush()
        tasks = [
            models.PipelineTask(photo_id=1, run_id=runs[0].id, phase="phase_1", task_name="vision_task", status="failed"),
            models.PipelineTask(photo_id=1, run_id=runs[0].id, phase="phase_1", task_name="auto_tag_clip_task", status="failed"),
            models.PipelineTask(photo_id=1, run_id=runs[0].id, phase="phase_2", task_name="translate_description_task", status="skipped", skip_reason="Prerequisite vision_task: failed"),
            models.PipelineTask(photo_id=1, run_id=runs[1].id, phase="phase_1", task_name="vision_task", status="done"),
            models.PipelineTask(photo_id=1, run_id=runs[1].id, phase="phase_1", task_name="auto_tag_clip_task", status="failed"),
            models.PipelineTask(photo_id=1, run_id=runs[1].id, phase="phase_2", task_name="translate_description_task", status="skipped", skip_reason="Prerequisite vision_task: failed"),
            models.PipelineTask(photo_id=2, run_id=runs[2].id, phase="phase_1", task_name="vision_task", status="interrupted"),
            models.PipelineTask(photo_id=2, run_id=runs[2].id, phase="phase_3", task_name="ocr_task", status="paused"),
            models.PipelineTask(photo_id=3, run_id=runs[3].id, phase="phase_1", task_name="vision_task", status="failed"),
            models.PipelineTask(photo_id=4, run_id=runs[4].id, phase="phase_1", task_name="auto_tag_clip_task", status="failed"),
            models.PipelineTask(photo_id=4, run_id=runs[5].id, phase="phase_1", task_name="auto_tag_clip_task", status="done"),
            models.PipelineTask(photo_id=5, run_id=runs[6].id, phase="phase_1", task_name="vision_task", status="failed"),
            models.PipelineTask(photo_id=6, run_id=runs[7].id, phase="phase_1", task_name="vision_task", status="canceled"),
        ]
        db.add_all(tasks)
        db.add(models.PipelineQueueEntry(run_id=runs[3].id, lane="local-ollama"))
        db.commit()

        result = queue.collect_retryable_tasks(db)

    assert result == {
        1: ["auto_tag_clip_task", "translate_description_task"],
        2: ["vision_task"],
    }


@pytest.mark.asyncio
async def test_queue_executes_a_selected_task_set_in_one_bounded_photo_run(queue_store, monkeypatch):
    queue, factory = queue_store
    import sys
    from types import SimpleNamespace

    selected = ["vision_task", "translate_description_task"]
    run_id = queue.enqueue_photo_run(1, "retry", retry_task_names=selected)
    with factory() as db:
        entry = db.get(models.PipelineQueueEntry, run_id)
        assert entry.retry_task_names == '["vision_task", "translate_description_task"]'

    executed = []

    async def retry_tasks(photo_id, task_names, *, run_id):
        executed.append((photo_id, task_names, run_id))
        with factory() as db:
            db.get(models.PipelineRun, run_id).status = "completed"
            db.commit()

    monkeypatch.setitem(sys.modules, "src.incoming_pipeline", SimpleNamespace(retry_pipeline_tasks=retry_tasks))
    await queue.execute_claimed_run(queue.claim_next_run())

    assert executed == [(1, selected, run_id)]


def test_queue_upgrade_adds_task_set_intent_without_losing_older_entries(queue_store):
    queue, factory = queue_store
    engine = factory.kw["bind"]
    run_id = queue.enqueue_photo_run(1, "retry", retry_task_name="vision_task")
    with engine.begin() as conn:
        conn.exec_driver_sql("ALTER TABLE pipeline_queue_entries DROP COLUMN retry_task_names")

    owner = queue.initialize_queue(engine)
    owner.close()

    from sqlalchemy import inspect

    columns = {column["name"] for column in inspect(engine).get_columns("pipeline_queue_entries")}
    assert "retry_task_names" in columns
    with factory() as db:
        entry = db.get(models.PipelineQueueEntry, run_id)
        assert entry.retry_task_name == "vision_task"
        assert entry.retry_task_names is None


def test_startup_retry_preference_defaults_off_and_admits_each_photo_once(queue_store):
    queue, factory = queue_store
    with factory() as db:
        old = models.PipelineRun(photo_id=1, source="manual", status="completed-with-errors")
        db.add(old)
        db.flush()
        db.add(
            models.PipelineTask(
                photo_id=1,
                run_id=old.id,
                phase="phase_1",
                task_name="auto_tag_clip_task",
                status="failed",
                error="tag persistence failed",
            )
        )
        db.commit()

    disabled = queue.enqueue_startup_retries()
    assert disabled == {"enabled": False, "queued_photos": 0, "queued_tasks": 0, "run_ids": []}
    with factory() as db:
        assert db.query(models.PipelineQueueEntry).count() == 0
        from src.db_service import set_setting

        set_setting(db, "retry_unfinished_at_startup", "true")

    enabled = queue.enqueue_startup_retries()
    assert enabled == {"enabled": True, "queued_photos": 1, "queued_tasks": 1, "run_ids": [2]}
    with factory() as db:
        entry = db.get(models.PipelineQueueEntry, enabled["run_ids"][0])
        assert entry.retry_task_names == '["auto_tag_clip_task"]'

    again = queue.enqueue_startup_retries()
    assert again == {"enabled": True, "queued_photos": 0, "queued_tasks": 0, "run_ids": []}


def test_bulk_recovery_admits_a_24_photo_backlog_once_and_keeps_it_bounded(queue_store):
    queue, factory = queue_store
    with factory() as db:
        runs = [
            models.PipelineRun(photo_id=photo_id, source="watcher", status="completed-with-errors")
            for photo_id in range(1, 25)
        ]
        db.add_all(runs)
        db.flush()
        for run in runs:
            db.add_all([
                models.PipelineTask(
                    photo_id=run.photo_id,
                    run_id=run.id,
                    phase="phase_1",
                    task_name="vision_task",
                    status="failed",
                    error="model stopped",
                ),
                models.PipelineTask(
                    photo_id=run.photo_id,
                    run_id=run.id,
                    phase="phase_2",
                    task_name="translate_description_task",
                    status="skipped",
                    skip_reason="Prerequisite vision_task: failed",
                ),
            ])
        db.commit()

    result = queue.enqueue_retryable_tasks(source="bulk-retry")

    assert result["queued_photos"] == 24
    assert result["queued_tasks"] == 48
    with factory() as db:
        admitted = db.query(models.PipelineRun).filter_by(source="bulk-retry").order_by(
            models.PipelineRun.photo_id
        ).all()
        assert [run.photo_id for run in admitted] == list(range(1, 25))
        assert all(run.status == "queued" for run in admitted)
        assert all(
            db.get(models.PipelineQueueEntry, run.id).retry_task_names
            == '["vision_task", "translate_description_task"]'
            for run in admitted
        )

    assert queue.claim_next_run() is not None
    assert queue.claim_next_run() is None
    assert queue.enqueue_retryable_tasks(source="bulk-retry") == {
        "queued_photos": 0,
        "queued_tasks": 0,
        "run_ids": [],
    }


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


def test_watcher_burst_admits_all_24_photos(queue_store, monkeypatch, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from pathlib import Path
    from types import SimpleNamespace

    queue, factory = queue_store
    from src import observer

    monkeypatch.setattr(observer, "SessionLocal", factory)
    monkeypatch.setattr(observer, "wait_until_file_ready", lambda path: True)
    monkeypatch.setattr(
        observer,
        "generate_file_hash",
        lambda path: str(int(Path(path).stem.removeprefix("photo-"))),
    )
    monkeypatch.setattr(observer, "get_photo_capture_date", lambda path: None)
    monkeypatch.setattr(observer, "move_photo", lambda path, destination: str(path))
    monkeypatch.setattr(
        observer, "check_photo_hash_exists", lambda db, file_hash: None
    )
    monkeypatch.setattr(
        observer,
        "create_photo_record",
        lambda db, file_hash, path, capture_date: db.get(models.Photo, int(file_hash)),
    )
    handler = observer.PhotoEventHandler(str(tmp_path))
    events = []
    for photo_id in range(1, 25):
        path = tmp_path / f"photo-{photo_id}.jpg"
        path.write_bytes(b"photo")
        events.append(SimpleNamespace(is_directory=False, src_path=str(path)))

    with ThreadPoolExecutor(max_workers=8) as workers:
        list(workers.map(handler.on_created, events))

    with factory() as db:
        admitted = db.query(models.PipelineRun).order_by(models.PipelineRun.photo_id).all()
        assert [(run.photo_id, run.source, run.status) for run in admitted] == [
            (photo_id, "watcher", "queued") for photo_id in range(1, 25)
        ]


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


def test_second_backend_cannot_recover_live_owner_work(queue_store):
    queue, factory = queue_store
    owner = queue.initialize_queue(factory.kw["bind"])
    try:
        run_id = queue.enqueue_photo_run(1, "watcher")
        queue.claim_next_run()
        with pytest.raises(RuntimeError, match="already owns"):
            queue.initialize_queue(factory.kw["bind"])
        with factory() as db:
            assert db.get(models.PipelineRun, run_id).status == "running"
        assert queue.enqueue_photo_run(1, "manual") == run_id
    finally:
        if owner is not None:
            owner.close()
    next_owner = queue.initialize_queue(factory.kw["bind"])
    try:
        with factory() as db:
            assert db.get(models.PipelineRun, run_id).status == "interrupted"
    finally:
        next_owner.close()


@pytest.mark.asyncio
async def test_cancel_drains_thread_writes_before_releasing_run(queue_store, monkeypatch):
    import asyncio
    import sys
    import threading
    from types import SimpleNamespace

    from src import pipeline_tracker as tracker
    from src.tasks import quality_tasks

    queue, factory = queue_store
    monkeypatch.setattr(tracker, "SessionLocal", factory)
    started, release = threading.Event(), threading.Event()

    def write_after_release(*args):
        started.set()
        release.wait(5)
        with factory() as db:
            db.get(models.Photo, 1).description = "worker finished"
            db.commit()

    monkeypatch.setattr(quality_tasks, "_quality_check_sync", write_after_release)

    async def execute(photo_id, scanner_id, *, run_id):
        with tracker.pipeline_run_context(run_id):
            tracker.init_pipeline_tasks(photo_id, "phase_0", ["brightness_task", "pending_work"])
            await quality_tasks.brightness_task(photo_id)

    monkeypatch.setitem(sys.modules, "src.incoming_pipeline", SimpleNamespace(start_pipeline=execute))
    first = queue.enqueue_photo_run(1, "manual")
    queue.enqueue_photo_run(2, "manual")
    task = asyncio.create_task(queue.run_scheduler())
    try:
        for _ in range(100):
            if started.is_set():
                break
            await asyncio.sleep(0.01)
        assert started.is_set()
        task.cancel()
        await asyncio.sleep(0.05)
        assert not task.done(), "cancellation released ownership while a worker can still write"
        task.cancel()
        await asyncio.sleep(0.01)
        assert not task.done(), "repeated cancellation must also drain worker writes"
        assert queue.claim_next_run() is None
        assert queue.enqueue_photo_run(1, "manual") == first
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
    with factory() as db:
        assert db.get(models.Photo, 1).description == "worker finished"
        assert db.get(models.PipelineRun, first).status == "interrupted"
        assert {t.status for t in db.query(models.PipelineTask).filter_by(run_id=first)} == {"interrupted"}
    assert queue.claim_next_run() is not None


def test_claim_reclassifies_queued_work_after_provider_switch(queue_store):
    queue, factory = queue_store
    with factory() as db:
        config = db.query(models.AIModelConfig).one()
        config.model_provider = "openai"
        config.url = "https://api.openai.com"
        db.commit()
    first = queue.enqueue_photo_run(1, "manual")
    queue.enqueue_photo_run(2, "manual")
    with factory() as db:
        config = db.query(models.AIModelConfig).one()
        config.model_provider = "ollama"
        config.url = "http://localhost:11434"
        db.commit()
    assert queue.claim_next_run().id == first
    assert queue.claim_next_run() is None, "stale cloud lane allowed two local Ollama runs"


def _hold_lifecycle_until_terminated(database_url, ready):
    import time

    from src.pipeline_queue import initialize_queue

    engine = create_engine(database_url)
    owner = initialize_queue(engine)
    ready.send(True)
    try:
        while True:
            time.sleep(1)
    finally:
        owner.close()


def test_lifecycle_owner_is_process_exclusive_and_crash_released(queue_store):
    import multiprocessing
    import time

    queue, factory = queue_store
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=_hold_lifecycle_until_terminated, args=(str(factory.kw["bind"].url), sender))
    process.start()
    try:
        assert receiver.poll(10), "child failed to acquire lifecycle ownership"
        assert receiver.recv() is True
        before = time.monotonic()
        with pytest.raises(RuntimeError, match="already owns"):
            queue.initialize_queue(factory.kw["bind"])
        assert time.monotonic() - before < 1, "second backend should fail promptly"
    finally:
        process.terminate()
        process.join(10)
        receiver.close()
        sender.close()
    assert not process.is_alive()
    owner = queue.initialize_queue(factory.kw["bind"])
    owner.close()


def test_configuration_save_and_claim_serialize(queue_store):
    import threading

    from src.db_service import ModelConfigurationBusyError, update_model_config
    from src.schemas import AIModelConfigUpdate

    queue, factory = queue_store
    for photo_id in range(1, 9):
        with factory() as db:
            config = db.query(models.AIModelConfig).one()
            config.model_provider = "openai"
            config.url = "https://api.openai.com"
            db.commit()
        run_id = queue.enqueue_photo_run(photo_id, "manual")
        barrier = threading.Barrier(2)

        def save():
            barrier.wait()
            with factory() as db:
                try:
                    update_model_config(
                        db,
                        "vision",
                        AIModelConfigUpdate(
                            mode="remote", model_provider="ollama", model_name="test", url="http://localhost:11434"
                        ),
                    )
                    return True
                except ModelConfigurationBusyError:
                    return False

        def claim():
            barrier.wait()
            return queue.claim_next_run()

        with ThreadPoolExecutor(max_workers=2) as workers:
            saved_future = workers.submit(save)
            claimed_future = workers.submit(claim)
            saved, claimed = saved_future.result(), claimed_future.result()
        assert claimed.id == run_id
        with factory() as db:
            assert db.get(models.PipelineQueueEntry, run_id).lane == ("local-ollama" if saved else "other")
            assert db.query(models.AIModelConfig).one().model_provider == ("ollama" if saved else "openai")
            db.get(models.PipelineRun, run_id).status = "completed"
            db.commit()
