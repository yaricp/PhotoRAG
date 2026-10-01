"""Run persistence and migration must preserve failed attempts and existing data."""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src import models
from src import pipeline_tracker as tracker


@pytest.fixture
def store(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'runs.db'}")
    models.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(tracker, "SessionLocal", factory)
    with factory() as db:
        photo = models.Photo(file_path="/test.jpg", hash="test", description="preserved")
        db.add(photo)
        db.commit()
        photo_id = photo.id
    yield engine, factory, photo_id
    engine.dispose()


@pytest.mark.asyncio
async def test_failed_run_survives_later_success(store):
    _, factory, photo_id = store
    assert hasattr(tracker, "create_pipeline_run"), "run persistence is missing"
    first = tracker.create_pipeline_run(photo_id, "manual")
    with tracker.pipeline_run_context(first):
        tracker.init_pipeline_tasks(photo_id, "phase_1", ["vision_task"])
        with pytest.raises(ValueError):
            async with tracker.track_task(photo_id, "phase_1", "vision_task"):
                raise ValueError("first failure")
    assert tracker.finalize_pipeline_run(first) == "completed-with-errors"
    second = tracker.create_pipeline_run(photo_id, "manual")
    with tracker.pipeline_run_context(second):
        tracker.init_pipeline_tasks(photo_id, "phase_1", ["vision_task"])
        async with tracker.track_task(photo_id, "phase_1", "vision_task"):
            pass
    assert tracker.finalize_pipeline_run(second) == "completed"
    with factory() as db:
        tasks = db.query(models.PipelineTask).order_by(models.PipelineTask.id).all()
        assert [(t.run_id, t.status, t.error) for t in tasks] == [
            (first, "failed", "first failure"),
            (second, "done", None),
        ]
        assert db.get(models.Photo, photo_id).description == "preserved"


@pytest.mark.parametrize(
    "initial_run_status,task_status,expected_run_status,finished",
    [
        ("queued", "pending", "queued", False),
        ("running", "pending", "running", False),
        ("running", "interrupted", "interrupted", True),
        ("running", "paused", "paused", False),
        ("paused", "pending", "paused", False),
        ("interrupted", "pending", "interrupted", True),
    ],
)
def test_finalization_preserves_lifecycle_states(store, initial_run_status, task_status, expected_run_status, finished):
    _, factory, photo_id = store
    run_id = tracker.create_pipeline_run(photo_id, "manual")
    with factory() as db:
        run = db.get(models.PipelineRun, run_id)
        run.status = initial_run_status
        db.add(
            models.PipelineTask(
                photo_id=photo_id,
                run_id=run_id,
                phase="phase_1",
                task_name="vision_task",
                status=task_status,
            )
        )
        db.commit()

    assert tracker.finalize_pipeline_run(run_id) == expected_run_status
    with factory() as db:
        run = db.get(models.PipelineRun, run_id)
        assert run.status == expected_run_status
        assert (run.finished_at is not None) is finished


def test_legacy_migration_preserves_rows_and_interrupts_unfinished_work(tmp_path):
    from src.db import database

    path = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE photos (id INTEGER PRIMARY KEY, description TEXT)"))
        conn.execute(text("INSERT INTO photos VALUES (1, 'precious'), (2, 'untouched')"))
        conn.execute(
            text(
                "CREATE TABLE pipeline_tasks (id INTEGER PRIMARY KEY, photo_id INTEGER, phase TEXT, task_name TEXT, status TEXT, error TEXT, started_at DATETIME, finished_at DATETIME, created_at DATETIME)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO pipeline_tasks VALUES (7, 1, 'phase_1', 'vision_task', 'failed', 'old error', NULL, NULL, '2026-09-01'), (8, 1, 'phase_2', 'translate_description_task', 'pending', NULL, NULL, NULL, '2026-09-01')"
            )
        )
    assert hasattr(database, "migrate_pipeline_runs"), "legacy run migration is missing"
    database.migrate_pipeline_runs(engine)
    database.migrate_pipeline_runs(engine)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT description FROM photos ORDER BY id")).scalars().all() == [
            "precious",
            "untouched",
        ]
        assert conn.execute(text("SELECT id, status, error FROM pipeline_tasks ORDER BY id")).all() == [
            (7, "failed", "old error"),
            (8, "interrupted", None),
        ]
        assert conn.execute(text("SELECT photo_id, status FROM pipeline_runs")).all() == [(1, "interrupted")]
        assert conn.execute(text("SELECT count(*) FROM pipeline_runs WHERE photo_id=2")).scalar() == 0
        assert conn.execute(text("SELECT count(*) FROM pipeline_tasks WHERE run_id IS NULL")).scalar() == 0
    assert path.with_suffix(".db.pre-pipeline-runs.bak").exists()


@pytest.mark.asyncio
async def test_failed_vision_skips_dependents_but_preserves_independent_success(store, monkeypatch):
    from src import incoming_pipeline as pipeline

    _, factory, photo_id = store

    async def successful(pid):
        return None

    async def failed(pid):
        raise RuntimeError("vision failed " + "x" * 3000)

    for name in pipeline._TASK_RUNNERS:
        monkeypatch.setattr(pipeline, name, failed if name == "vision_task" else successful)
    await pipeline.start_pipeline(photo_id)
    with factory() as db:
        run = db.query(models.PipelineRun).one()
        tasks = {t.task_name: t for t in db.query(models.PipelineTask)}
        assert run.status == "completed-with-errors"
        assert len(run.summary) <= 2000
        assert tasks["vision_task"].status == "failed"
        assert tasks["auto_tag_clip_task"].status == "done"
        for name in ("translate_description_task", "final_embedding_task"):
            assert tasks[name].status == "skipped"
            assert "vision_task" in tasks[name].skip_reason


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "is_doc,ocr_text,expected", [(False, None, "completed"), (True, None, "completed-with-errors")]
)
async def test_document_embedding_no_output_is_explicit_skip(store, monkeypatch, is_doc, ocr_text, expected):
    from src.tasks import embedding_tasks

    _, factory, photo_id = store
    monkeypatch.setattr(embedding_tasks, "_read_doc_input_sync", lambda pid: (is_doc, ocr_text))
    run_id = tracker.create_pipeline_run(photo_id, "manual")
    with tracker.pipeline_run_context(run_id):
        tracker.init_pipeline_tasks(photo_id, "phase_4", ["embedding_document_text_task"])
        await embedding_tasks.embedding_document_text_task(photo_id)
    assert tracker.finalize_pipeline_run(run_id) == expected
    with factory() as db:
        task = db.query(models.PipelineTask).one()
        assert task.status == "skipped"
        assert task.skip_reason


@pytest.mark.asyncio
async def test_translation_in_english_is_inapplicable(store, monkeypatch):
    from src.tasks import translation_tasks

    _, factory, photo_id = store
    monkeypatch.setattr(translation_tasks, "_get_target_language", lambda: "en")
    run_id = tracker.create_pipeline_run(photo_id, "manual")
    with tracker.pipeline_run_context(run_id):
        tracker.init_pipeline_tasks(photo_id, "phase_2", ["translate_description_task"])
        await translation_tasks.translate_description_task(photo_id)
    assert tracker.finalize_pipeline_run(run_id) == "completed"
    with factory() as db:
        task = db.query(models.PipelineTask).one()
        assert task.status == "skipped"
        assert task.skip_reason


@pytest.mark.asyncio
async def test_description_retry_keeps_evidence_and_tags_and_refreshes_dependents(store, monkeypatch):
    from src import incoming_pipeline as pipeline

    _, factory, photo_id = store
    first = tracker.create_pipeline_run(photo_id, "manual")
    with tracker.pipeline_run_context(first):
        tracker.init_pipeline_tasks(photo_id, "phase_1", ["vision_task", "auto_tag_clip_task"])
        with pytest.raises(ValueError):
            async with tracker.track_task(photo_id, "phase_1", "vision_task"):
                raise ValueError("original failure")
        async with tracker.track_task(photo_id, "phase_1", "auto_tag_clip_task"):
            pass
    tracker.finalize_pipeline_run(first)
    with factory() as db:
        tag = models.Tag(name="independent")
        db.add(tag)
        db.flush()
        db.add(models.PhotoTag(photo_id=photo_id, tag_id=tag.id))
        db.commit()

    async def describe(pid):
        with factory() as db:
            db.get(models.Photo, pid).description = "new description"
            db.commit()

    async def translate(pid):
        with factory() as db:
            photo = db.get(models.Photo, pid)
            photo.translated_description = "translated " + photo.description
            db.commit()

    async def embed(pid):
        with factory() as db:
            photo = db.get(models.Photo, pid)
            photo.ocr_text = "embedding input: " + photo.description
            db.commit()

    monkeypatch.setattr(
        pipeline,
        "_TASK_RUNNERS",
        {"vision_task": describe, "translate_description_task": translate, "final_embedding_task": embed},
    )
    await pipeline.retry_pipeline_task(photo_id, "vision_task")
    with factory() as db:
        tasks = db.query(models.PipelineTask).filter_by(task_name="vision_task").order_by(models.PipelineTask.id).all()
        assert len(tasks) == 2
        assert tasks[0].error == "original failure"
        assert tasks[0].status == "failed"
        assert tasks[1].status == "done"
        assert tasks[1].run_id != first
        photo = db.get(models.Photo, photo_id)
        assert photo.translated_description == "translated new description"
        assert photo.ocr_text == "embedding input: new description"
        assert [relation.tag.name for relation in photo.tags_rel] == ["independent"]
        assert db.get(models.PipelineRun, first).status == "completed-with-errors"
        assert db.get(models.PipelineRun, tasks[1].run_id).status == "completed"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name",
    [
        "vision_task",
        "is_this_document_task",
        "ocr_task",
        "translate_description_task",
        "final_embedding_task",
        "auto_tag_clip_task",
        "categorize_photo_task",
    ],
)
async def test_missing_prerequisites_never_report_generated_output(store, monkeypatch, name):
    from src import incoming_pipeline as pipeline
    from src.tasks import clip_tasks, embedding_tasks, translation_tasks, vision_tasks

    _, factory, photo_id = store
    monkeypatch.setattr(vision_tasks, "_get_vision_input_sync", lambda pid: None)
    monkeypatch.setattr(vision_tasks, "_get_doc_input_sync", lambda pid: (None, False))
    monkeypatch.setattr(translation_tasks, "_get_target_language", lambda: "fr")
    monkeypatch.setattr(translation_tasks, "_get_description_sync", lambda pid: None)
    monkeypatch.setattr(embedding_tasks, "_read_embedding_input_sync", lambda pid: None)
    monkeypatch.setattr(clip_tasks, "_get_file_path_sync", lambda pid: None)
    run = tracker.create_pipeline_run(photo_id, "manual")
    phase = pipeline._TASK_PHASES[name]
    with tracker.pipeline_run_context(run):
        tracker.init_pipeline_tasks(photo_id, phase, [name])
        await pipeline._TASK_RUNNERS[name](photo_id)
    assert tracker.finalize_pipeline_run(run) == "completed-with-errors"
    with factory() as db:
        task = db.query(models.PipelineTask).one()
        assert task.status == "skipped"
        assert task.skip_reason


@pytest.mark.asyncio
async def test_ocr_non_document_is_legitimately_inapplicable(store, monkeypatch):
    from src.tasks import vision_tasks

    _, factory, photo_id = store
    monkeypatch.setattr(vision_tasks, "_get_doc_input_sync", lambda pid: ("/test.jpg", False))
    run = tracker.create_pipeline_run(photo_id, "manual")
    with tracker.pipeline_run_context(run):
        tracker.init_pipeline_tasks(photo_id, "phase_3", ["ocr_task"])
        await vision_tasks.ocr_task(photo_id)
    assert tracker.finalize_pipeline_run(run) == "completed"
    with factory() as db:
        assert db.query(models.PipelineTask).one().status == "skipped"


@pytest.mark.asyncio
async def test_empty_vision_response_is_failure(store, monkeypatch):
    from src.tasks import vision_tasks

    _, factory, photo_id = store
    monkeypatch.setattr(vision_tasks, "_get_vision_input_sync", lambda pid: "/test.jpg")

    async def empty(**kwargs):
        return "  "

    monkeypatch.setattr(vision_tasks, "call_vision_model", empty)
    monkeypatch.setattr(vision_tasks, "SessionLocal", factory)
    run = tracker.create_pipeline_run(photo_id, "manual")
    with tracker.pipeline_run_context(run):
        tracker.init_pipeline_tasks(photo_id, "phase_1", ["vision_task"])
        with pytest.raises(ValueError, match="Empty"):
            await vision_tasks.vision_task(photo_id)
    assert tracker.finalize_pipeline_run(run) == "completed-with-errors"
    with factory() as db:
        assert db.get(models.Photo, photo_id).description == "preserved"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name", ["is_this_document_task", "ocr_task", "translate_description_task", "final_embedding_task"]
)
async def test_empty_required_model_output_fails(store, monkeypatch, name):
    from src import incoming_pipeline as pipeline
    from src.tasks import embedding_tasks, translation_tasks, vision_tasks

    _, factory, photo_id = store

    async def empty(*args, **kwargs):
        return ""

    monkeypatch.setattr(vision_tasks, "SessionLocal", factory)
    monkeypatch.setattr(translation_tasks, "SessionLocal", factory)
    monkeypatch.setattr(vision_tasks, "_get_vision_input_sync", lambda pid: "/test.jpg")
    monkeypatch.setattr(vision_tasks, "_get_doc_input_sync", lambda pid: ("/test.jpg", True))
    monkeypatch.setattr(vision_tasks, "call_vision_model", empty)
    monkeypatch.setattr(vision_tasks, "call_ocr_model", empty)
    monkeypatch.setattr(translation_tasks, "_get_target_language", lambda: "fr")
    monkeypatch.setattr(translation_tasks, "_get_description_sync", lambda pid: "description")
    monkeypatch.setattr(translation_tasks, "call_translation_model", empty)
    monkeypatch.setattr(
        embedding_tasks,
        "_read_embedding_input_sync",
        lambda pid: {"description": "description", "tags": [], "categories": [], "location": None},
    )
    monkeypatch.setattr(embedding_tasks, "call_embedding_model", empty)
    # Model output is validated before persistence; no external vector DB is needed.
    monkeypatch.setattr(embedding_tasks, "_save_embedding_sync", lambda *args: None)
    run = tracker.create_pipeline_run(photo_id, "manual")
    with tracker.pipeline_run_context(run):
        tracker.init_pipeline_tasks(photo_id, pipeline._TASK_PHASES[name], [name])
        with pytest.raises(ValueError, match="Empty"):
            await pipeline._TASK_RUNNERS[name](photo_id)
    assert tracker.finalize_pipeline_run(run) == "completed-with-errors"


@pytest.mark.asyncio
async def test_quality_check_exception_is_not_swallowed(store, monkeypatch):
    from src.tasks import quality_tasks

    _, factory, photo_id = store
    monkeypatch.setattr(quality_tasks, "SessionLocal", factory)

    def broken(path):
        raise ValueError("Cannot decode image")

    monkeypatch.setattr(quality_tasks, "check_blur", broken)
    run = tracker.create_pipeline_run(photo_id, "manual")
    with tracker.pipeline_run_context(run):
        tracker.init_pipeline_tasks(photo_id, "phase_0", ["blur_task"])
        with pytest.raises(ValueError, match="Cannot decode"):
            await quality_tasks.blur_task(photo_id)
    assert tracker.finalize_pipeline_run(run) == "completed-with-errors"


@pytest.mark.asyncio
async def test_retry_is_running_during_execution_and_retains_failed_attempt(store, monkeypatch):
    from src import incoming_pipeline as pipeline

    _, factory, photo_id = store

    async def failed(pid):
        with factory() as db:
            run = db.query(models.PipelineRun).order_by(models.PipelineRun.id.desc()).first()
            assert run.status == "running"
            assert run.started_at is not None
        raise RuntimeError("retry failed")

    monkeypatch.setitem(pipeline._TASK_RUNNERS, "metadata_task", failed)
    await pipeline.retry_pipeline_task(photo_id, "metadata_task")
    await pipeline.retry_pipeline_task(photo_id, "metadata_task")
    with factory() as db:
        assert [t.error for t in db.query(models.PipelineTask).order_by(models.PipelineTask.id)] == [
            "retry failed",
            "retry failed",
        ]
        assert [r.status for r in db.query(models.PipelineRun)] == ["completed-with-errors", "completed-with-errors"]


@pytest.mark.asyncio
@pytest.mark.parametrize("translated", ["", " \t\n"])
async def test_document_embedding_rejects_empty_translation_before_vector_persistence(store, monkeypatch, translated):
    from src.tasks import embedding_tasks

    _, factory, photo_id = store
    monkeypatch.setattr(embedding_tasks, "SessionLocal", factory)
    monkeypatch.setattr(embedding_tasks, "_read_doc_input_sync", lambda pid: (True, "Document text"))
    persisted_vectors = []

    async def translate(*args, **kwargs):
        return translated

    async def embed(*args, **kwargs):
        return [0.5, 0.5]

    monkeypatch.setattr(embedding_tasks, "call_translation_model", translate)
    monkeypatch.setattr(embedding_tasks, "call_embedding_model", embed)
    monkeypatch.setattr(embedding_tasks, "_save_embedding_sync", lambda *args: persisted_vectors.append(args))
    run = tracker.create_pipeline_run(photo_id, "manual")
    with tracker.pipeline_run_context(run):
        tracker.init_pipeline_tasks(photo_id, "phase_4", ["embedding_document_text_task"])
        try:
            await embedding_tasks.embedding_document_text_task(photo_id)
        except ValueError:
            pass
    assert persisted_vectors == [], "Invalid translated text must never replace a stored vector"
    assert tracker.finalize_pipeline_run(run) == "completed-with-errors"
    with factory() as db:
        task = db.query(models.PipelineTask).one()
        assert task.status == "failed"
        assert "Empty" in task.error
