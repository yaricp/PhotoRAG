import sys

import pytest

from tests.test_pipeline_runs import store


def import_real_incoming_pipeline():
    for module_name in ["src.incoming_pipeline", "src.tasks"]:
        if module_name in sys.modules and not hasattr(sys.modules[module_name], "__file__"):
            sys.modules.pop(module_name, None)
    from src import incoming_pipeline

    if not hasattr(incoming_pipeline, "retry_pipeline_task") or not hasattr(incoming_pipeline, "__file__"):
        sys.modules.pop("src.incoming_pipeline", None)
        from src import incoming_pipeline as reloaded

        return reloaded
    return incoming_pipeline


@pytest.mark.asyncio
async def test_retry_pipeline_task_runs_registered_runner(monkeypatch, store):  # noqa: F811 - shared pytest fixture
    incoming_pipeline = import_real_incoming_pipeline()

    _, factory, photo_id = store
    calls = []

    async def fake_runner(photo_id: int) -> None:
        calls.append(photo_id)

    monkeypatch.setattr(incoming_pipeline, "_TASK_RUNNERS", {"metadata_task": fake_runner})

    await incoming_pipeline.retry_pipeline_task(photo_id, "metadata_task")

    assert calls == [photo_id]
    assert incoming_pipeline.is_retryable_pipeline_task("metadata_task") is True


@pytest.mark.asyncio
async def test_retry_pipeline_task_rejects_unknown_task(monkeypatch):
    incoming_pipeline = import_real_incoming_pipeline()

    monkeypatch.setattr(incoming_pipeline, "_TASK_RUNNERS", {})

    with pytest.raises(ValueError, match="Unsupported pipeline task"):
        await incoming_pipeline.retry_pipeline_task(123, "missing_task")


@pytest.mark.asyncio
async def test_retry_pipeline_tasks_runs_only_selected_attempts_in_dependency_order(monkeypatch, store):  # noqa: F811 - shared pytest fixture
    incoming_pipeline = import_real_incoming_pipeline()
    _, factory, photo_id = store
    from src.models import PipelineRun, PipelineTask
    from src.pipeline_tracker import create_pipeline_run

    with factory() as db:
        previous = PipelineRun(photo_id=photo_id, source="manual", status="completed-with-errors")
        db.add(previous)
        db.flush()
        db.add_all(
            [
                PipelineTask(
                    photo_id=photo_id,
                    run_id=previous.id,
                    phase="phase_1",
                    task_name="vision_task",
                    status="failed",
                    error="old error",
                ),
                PipelineTask(
                    photo_id=photo_id,
                    run_id=previous.id,
                    phase="phase_2",
                    task_name="translate_description_task",
                    status="skipped",
                    skip_reason="Prerequisite vision_task: failed",
                ),
            ]
        )
        db.commit()
        previous_id = previous.id
        previous_task_id = (
            db.query(PipelineTask.id)
            .filter_by(
                run_id=previous_id,
                task_name="vision_task",
            )
            .scalar()
        )

    calls = []

    def succeed(task_name):
        async def runner(_photo_id):
            calls.append(task_name)

        return runner

    monkeypatch.setattr(
        incoming_pipeline,
        "_TASK_RUNNERS",
        {
            "auto_tag_clip_task": succeed("auto_tag_clip_task"),
            "vision_task": succeed("vision_task"),
            "translate_description_task": succeed("translate_description_task"),
        },
    )
    run_id = create_pipeline_run(photo_id, "bulk-retry")
    await incoming_pipeline.retry_pipeline_tasks(
        photo_id,
        ["vision_task", "translate_description_task"],
        run_id=run_id,
    )

    assert calls == ["vision_task", "translate_description_task"]
    with factory() as db:
        assert db.get(PipelineRun, previous_id).status == "completed-with-errors"
        assert db.get(PipelineTask, previous_task_id).status == "failed"
        attempts = db.query(PipelineTask).filter_by(run_id=run_id).order_by(PipelineTask.id).all()
        assert [(task.task_name, task.status) for task in attempts] == [
            ("vision_task", "done"),
            ("translate_description_task", "done"),
        ]
