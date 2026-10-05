from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from PIL import Image


@pytest.mark.parametrize(
    'task_name',
    [
        'auto_tag_clip_task',
        'categorize_photo_task',
        'vision_task',
        'final_embedding_task',
        'is_this_document_task',
        'translate_description_task',
        'ocr_task',
        'embedding_document_text_task',
    ],
)
@pytest.mark.asyncio
async def test_uniform_image_skips_every_model_task(monkeypatch, tmp_path, task_name):
    from src import incoming_pipeline

    image_path = tmp_path / 'uniform.png'
    Image.new('RGB', (32, 32), (128, 128, 128)).save(image_path)

    @asynccontextmanager
    async def fake_track_task(*_args, **_kwargs):
        yield

    async def direct_thread(function, *args, **kwargs):
        return function(*args, **kwargs)

    skip = MagicMock()
    runner = AsyncMock()
    monkeypatch.setattr(incoming_pipeline, '_get_file_path_sync', lambda _photo_id: str(image_path))
    monkeypatch.setattr(incoming_pipeline, 'run_in_thread', direct_thread)
    monkeypatch.setattr(incoming_pipeline, 'track_task', fake_track_task)
    monkeypatch.setattr(incoming_pipeline, 'mark_task_skipped', skip)

    await incoming_pipeline._run_task(19, 'phase_1', task_name, runner)

    runner.assert_not_awaited()
    skip.assert_called_once_with(
        19,
        'phase_1',
        task_name,
        'Image is completely uniform; AI processing was skipped.',
        required=False,
    )


@pytest.mark.asyncio
async def test_model_free_task_still_runs_for_uniform_image(monkeypatch):
    from src import incoming_pipeline

    @asynccontextmanager
    async def fake_track_task(*_args, **_kwargs):
        yield

    runner = AsyncMock()
    monkeypatch.setattr(incoming_pipeline, 'track_task', fake_track_task)
    monkeypatch.setattr(incoming_pipeline, 'mark_task_skipped', MagicMock())

    await incoming_pipeline._run_task(19, 'phase_3', 'screenshot_detect_task', runner)

    runner.assert_awaited_once_with(19)
