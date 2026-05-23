"""
TDD tests for retranslation_pipeline.py — Phase 8.3.

Verifies that:
- start_retranslation is a no-op for English
- Each photo gets a PipelineTask row with phase="retranslation"
- translate_description_task_for_retranslation writes to translated_description
- API endpoint POST /api/translation/retranslate-all returns 202
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_photo(photo_id: int, description: str = "A sunny beach") -> MagicMock:
    photo = MagicMock()
    photo.id = photo_id
    photo.description = description
    photo.translated_description = None
    return photo


# ---------------------------------------------------------------------------
# start_retranslation
# ---------------------------------------------------------------------------

class TestStartRetranslation:
    @pytest.mark.asyncio
    async def test_skips_entirely_when_language_is_english(self):
        from src.retranslation_pipeline import start_retranslation
        with patch("src.retranslation_pipeline.init_pipeline_tasks") as mock_init, \
             patch("src.retranslation_pipeline.SessionLocal"):
            await start_retranslation("en")
        mock_init.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_entirely_when_no_photos(self):
        from src.retranslation_pipeline import start_retranslation
        mock_db = MagicMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        with patch("src.retranslation_pipeline.init_pipeline_tasks") as mock_init, \
             patch("src.retranslation_pipeline.SessionLocal", return_value=MagicMock(
                 __enter__=lambda s, *a: mock_db,
                 __exit__=lambda s, *a: None,
             )):
            await start_retranslation("ru")
        mock_init.assert_not_called()

    @pytest.mark.asyncio
    async def test_creates_pipeline_task_per_photo(self):
        from src.retranslation_pipeline import start_retranslation

        mock_db = MagicMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = [1, 2, 3]

        translate_calls = []

        async def fake_translate(photo_id, target_lang):
            translate_calls.append((photo_id, target_lang))

        with patch("src.retranslation_pipeline.init_pipeline_tasks") as mock_init, \
             patch("src.retranslation_pipeline.SessionLocal") as mock_sl, \
             patch("src.retranslation_pipeline.translate_description_task_for_retranslation",
                   side_effect=fake_translate):
            mock_sl.return_value.__enter__ = lambda s: mock_db
            mock_sl.return_value.__exit__ = MagicMock(return_value=False)
            await start_retranslation("es")

        assert mock_init.call_count == 3
        for c in mock_init.call_args_list:
            assert c.args[1] == "retranslation"
            assert "translate_description_task" in c.args[2]

    @pytest.mark.asyncio
    async def test_passes_correct_language_to_translate_task(self):
        from src.retranslation_pipeline import start_retranslation

        mock_db = MagicMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = [7]

        translate_calls = []

        async def fake_translate(photo_id, target_lang):
            translate_calls.append((photo_id, target_lang))

        with patch("src.retranslation_pipeline.init_pipeline_tasks"), \
             patch("src.retranslation_pipeline.SessionLocal") as mock_sl, \
             patch("src.retranslation_pipeline.translate_description_task_for_retranslation",
                   side_effect=fake_translate):
            mock_sl.return_value.__enter__ = lambda s: mock_db
            mock_sl.return_value.__exit__ = MagicMock(return_value=False)
            await start_retranslation("ru")

        assert translate_calls == [(7, "ru")]


# ---------------------------------------------------------------------------
# translate_description_task_for_retranslation
# ---------------------------------------------------------------------------

class TestTranslateDescriptionTaskForRetranslation:
    @pytest.mark.asyncio
    async def test_saves_translation_to_db(self):
        from src.tasks.translation_tasks import translate_description_task_for_retranslation

        with patch("src.tasks.translation_tasks._get_description_sync", return_value="A cat"), \
             patch("src.tasks.translation_tasks._save_translation_sync") as mock_save, \
             patch("src.tasks.translation_tasks.call_translation_model",
                   new_callable=AsyncMock, return_value="Un gato"), \
             patch("src.tasks.translation_tasks.track_task") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=None)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            await translate_description_task_for_retranslation(42, "es")

        mock_save.assert_called_once_with(42, "Un gato")

    @pytest.mark.asyncio
    async def test_uses_retranslation_phase_name(self):
        from src.tasks.translation_tasks import translate_description_task_for_retranslation

        with patch("src.tasks.translation_tasks._get_description_sync", return_value="Hello"), \
             patch("src.tasks.translation_tasks._save_translation_sync"), \
             patch("src.tasks.translation_tasks.call_translation_model",
                   new_callable=AsyncMock, return_value="Hola"), \
             patch("src.tasks.translation_tasks.track_task") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=None)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            await translate_description_task_for_retranslation(1, "es")

        mock_ctx.assert_called_once_with(1, "retranslation", "translate_description_task")

    @pytest.mark.asyncio
    async def test_skips_photo_with_no_description(self):
        from src.tasks.translation_tasks import translate_description_task_for_retranslation

        with patch("src.tasks.translation_tasks._get_description_sync", return_value=None), \
             patch("src.tasks.translation_tasks.call_translation_model",
                   new_callable=AsyncMock) as mock_translate, \
             patch("src.tasks.translation_tasks.track_task") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=None)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            await translate_description_task_for_retranslation(99, "ru")

        mock_translate.assert_not_called()


# ---------------------------------------------------------------------------
# API endpoint: POST /api/translation/retranslate-all
# ---------------------------------------------------------------------------

class TestRetranslateAllEndpoint:
    def test_returns_202_and_started_status(self):
        from fastapi.testclient import TestClient
        from src.main import app

        with patch("src.main.get_setting", return_value="es"), \
             patch("src.retranslation_pipeline.start_retranslation", new_callable=AsyncMock):
            client = TestClient(app)
            resp = client.post(
                "/api/translation/retranslate-all",
                headers={"Authorization": "Bearer secret"},
            )

        assert resp.status_code == 202
        assert resp.json()["status"] == "started"

    def test_does_not_start_pipeline_when_language_is_english(self):
        from fastapi.testclient import TestClient
        from src.main import app

        with patch("src.main.get_setting", return_value="en"), \
             patch("src.retranslation_pipeline.start_retranslation",
                   new_callable=AsyncMock) as mock_start:
            client = TestClient(app)
            resp = client.post(
                "/api/translation/retranslate-all",
                headers={"Authorization": "Bearer secret"},
            )

        assert resp.status_code == 202
        mock_start.assert_not_called()
