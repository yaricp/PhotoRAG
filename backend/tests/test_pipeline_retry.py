import pytest


@pytest.mark.asyncio
async def test_retry_pipeline_task_runs_registered_runner(monkeypatch):
    from src import incoming_pipeline

    calls = []

    async def fake_runner(photo_id: int) -> None:
        calls.append(photo_id)

    monkeypatch.setattr(incoming_pipeline, "_TASK_RUNNERS", {"fake_task": fake_runner})

    await incoming_pipeline.retry_pipeline_task(123, "fake_task")

    assert calls == [123]
    assert incoming_pipeline.is_retryable_pipeline_task("fake_task") is True


@pytest.mark.asyncio
async def test_retry_pipeline_task_rejects_unknown_task(monkeypatch):
    from src import incoming_pipeline

    monkeypatch.setattr(incoming_pipeline, "_TASK_RUNNERS", {})

    with pytest.raises(ValueError, match="Unsupported pipeline task"):
        await incoming_pipeline.retry_pipeline_task(123, "missing_task")
