import sys

import pytest


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
async def test_retry_pipeline_task_runs_registered_runner(monkeypatch):
    incoming_pipeline = import_real_incoming_pipeline()

    calls = []

    async def fake_runner(photo_id: int) -> None:
        calls.append(photo_id)

    monkeypatch.setattr(incoming_pipeline, "_TASK_RUNNERS", {"fake_task": fake_runner})

    await incoming_pipeline.retry_pipeline_task(123, "fake_task")

    assert calls == [123]
    assert incoming_pipeline.is_retryable_pipeline_task("fake_task") is True


@pytest.mark.asyncio
async def test_retry_pipeline_task_rejects_unknown_task(monkeypatch):
    incoming_pipeline = import_real_incoming_pipeline()

    monkeypatch.setattr(incoming_pipeline, "_TASK_RUNNERS", {})

    with pytest.raises(ValueError, match="Unsupported pipeline task"):
        await incoming_pipeline.retry_pipeline_task(123, "missing_task")
