"""
TDD tests for src/model_services.py.

Strategy:
- All Huey task calls are mocked — we never actually enqueue tasks.
- _poll_result is mocked to return a pre-set JSON string synchronously.
- _call_remote is mocked for remote-mode paths.
- DB mode lookup is patched via read_model_config_from_db.

The queue modules (clip_queue, vision_queue, etc.) use lazy imports inside
model_services.py functions. We pre-import them here so unittest.mock.patch
can resolve and replace their attributes during tests.
"""
import json
import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

# Pre-import queue modules so patch() can resolve them.
# Each module only creates a SqliteHuey object at import time (safe);
# actual model loading is deferred to _get_model() inside worker processes.
import src.queues.clip_queue          # noqa: F401
import src.queues.vision_queue        # noqa: F401
import src.queues.embedding_queue     # noqa: F401
import src.queues.translation_queue   # noqa: F401
import src.queues.ocr_queue           # noqa: F401


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_result(payload) -> str:
    """Serialize a Python object as the JSON string poll would return."""
    return json.dumps(payload)


_poll_store: dict[str, str] = {}


async def _instant_poll(task_id: str, label: str = "") -> str:
    """Replacement for _wait_result that resolves immediately."""
    return _poll_store["value"]


def _set_poll_value(value: str) -> None:
    _poll_store["value"] = value


# ---------------------------------------------------------------------------
# _get_mode
# ---------------------------------------------------------------------------

class TestGetMode:
    def test_returns_db_mode_when_present(self):
        from src.model_services import _get_mode
        from src.config import CLIP_Settings

        with patch("src.model_services.read_model_config_from_db",
                   return_value={"mode": "remote", "model_name": "some-model"}):
            assert _get_mode("clip", CLIP_Settings()) == "remote"

    def test_falls_back_to_settings_when_db_returns_none(self):
        from src.model_services import _get_mode
        from src.config import CLIP_Settings

        with patch("src.model_services.read_model_config_from_db", return_value=None):
            settings = CLIP_Settings()
            settings.CLIP_MODE = "local"
            assert _get_mode("clip", settings) == "local"

    def test_falls_back_to_translation_mode_attr_as_last_resort(self):
        """When neither DB nor a typed attribute exists, uses TRANSLATION_MODE."""
        from src.model_services import _get_mode
        from src.config import Translation_Settings

        with patch("src.model_services.read_model_config_from_db", return_value=None):
            settings = Translation_Settings()
            result = _get_mode("translator", settings)
            assert result in ("local", "remote")


# ---------------------------------------------------------------------------
# call_clip_model — local mode
# ---------------------------------------------------------------------------

class TestCallClipModelLocal:
    @pytest.mark.asyncio
    async def test_local_tags_submits_huey_task_and_returns_deserialized(self):
        tags = [["cat", 0.9], ["animal", 0.8]]
        _set_poll_value(_make_result(tags))

        fake_task_fn = MagicMock()

        with (
            patch("src.model_services.read_model_config_from_db",
                  return_value={"mode": "local"}),
            patch("src.model_services._wait_result", side_effect=_instant_poll),
            patch("src.queues.clip_queue.call_local_clip_model", fake_task_fn),
        ):
            from src.model_services import call_clip_model
            result = await call_clip_model("/tmp/photo.jpg", task="tags")

        assert result == tags
        fake_task_fn.assert_called_once()
        call_args = fake_task_fn.call_args[0]
        assert call_args[1] == "/tmp/photo.jpg"
        assert call_args[2] == "tags"

    @pytest.mark.asyncio
    async def test_local_encode_image_returns_float_list(self):
        vector = [0.1, 0.2, 0.3]
        _set_poll_value(_make_result(vector))

        fake_task_fn = MagicMock()

        with (
            patch("src.model_services.read_model_config_from_db",
                  return_value={"mode": "local"}),
            patch("src.model_services._wait_result", side_effect=_instant_poll),
            patch("src.queues.clip_queue.call_local_clip_model", fake_task_fn),
        ):
            from src.model_services import call_clip_model
            result = await call_clip_model("/tmp/photo.jpg", task="encode_image")

        assert result == vector

    @pytest.mark.asyncio
    async def test_local_error_propagates_as_runtime_error(self):
        from src.model_services import call_clip_model

        async def _raise(_task_id, label=""):
            raise RuntimeError("model exploded")

        with (
            patch("src.model_services.read_model_config_from_db",
                  return_value={"mode": "local"}),
            patch("src.model_services._wait_result", side_effect=_raise),
            patch("src.queues.clip_queue.call_local_clip_model", MagicMock()),
        ):
            with pytest.raises(RuntimeError, match="model exploded"):
                await call_clip_model("/tmp/photo.jpg", task="tags")


# ---------------------------------------------------------------------------
# call_clip_model — remote mode
# ---------------------------------------------------------------------------

class TestCallClipModelRemote:
    @pytest.mark.asyncio
    async def test_remote_mode_calls_remote_clip(self):
        tags = [["dog", 0.95]]
        mock_remote = AsyncMock(return_value=tags)

        with (
            patch("src.model_services.read_model_config_from_db",
                  return_value={"mode": "remote"}),
            patch("src.model_services._call_remote_clip", mock_remote),
        ):
            from src.model_services import call_clip_model
            result = await call_clip_model("/tmp/photo.jpg", task="tags")

        assert result == tags
        mock_remote.assert_awaited_once()


# ---------------------------------------------------------------------------
# call_vision_model
# ---------------------------------------------------------------------------

class TestCallVisionModel:
    @pytest.mark.asyncio
    async def test_local_describe_scene_returns_text(self):
        _set_poll_value(_make_result({"text": "A sunny beach."}))
        fake_task_fn = MagicMock()

        with (
            patch("src.model_services.read_model_config_from_db",
                  return_value={"mode": "local"}),
            patch("src.model_services._wait_result", side_effect=_instant_poll),
            patch("src.queues.vision_queue.call_local_vision_model", fake_task_fn),
        ):
            from src.model_services import call_vision_model
            result = await call_vision_model("/tmp/photo.jpg", "describe_scene")

        assert result == "A sunny beach."
        fake_task_fn.assert_called_once()

    @pytest.mark.asyncio
    async def test_local_is_document_returns_yes_no(self):
        _set_poll_value(_make_result({"text": "yes"}))
        fake_task_fn = MagicMock()

        with (
            patch("src.model_services.read_model_config_from_db",
                  return_value={"mode": "local"}),
            patch("src.model_services._wait_result", side_effect=_instant_poll),
            patch("src.queues.vision_queue.call_local_vision_model", fake_task_fn),
        ):
            from src.model_services import call_vision_model
            result = await call_vision_model("/tmp/photo.jpg", "is_document")

        assert result == "yes"

    @pytest.mark.asyncio
    async def test_remote_vision_returns_text(self):
        mock_remote = AsyncMock(return_value="Mountain landscape.")

        with (
            patch("src.model_services.read_model_config_from_db",
                  return_value={"mode": "remote", "model_name": "gpt-4o"}),
            patch("src.model_services._call_remote_vision", mock_remote),
        ):
            from src.model_services import call_vision_model
            result = await call_vision_model("/tmp/photo.jpg", "describe_scene")

        assert result == "Mountain landscape."


# ---------------------------------------------------------------------------
# call_embedding_model
# ---------------------------------------------------------------------------

class TestCallEmbeddingModel:
    @pytest.mark.asyncio
    async def test_local_returns_float_list(self):
        vector = [0.01, -0.5, 0.99]
        _set_poll_value(_make_result(vector))
        fake_task_fn = MagicMock()

        with (
            patch("src.model_services.read_model_config_from_db",
                  return_value={"mode": "local"}),
            patch("src.model_services._wait_result", side_effect=_instant_poll),
            patch("src.queues.embedding_queue.call_local_embedding_model", fake_task_fn),
        ):
            from src.model_services import call_embedding_model
            result = await call_embedding_model("some text", purpose="save")

        assert result == vector
        call_args = fake_task_fn.call_args[0]
        # Prefix is applied before dispatching to the queue for nomic models;
        # for a default (non-nomic) model_name the text passes through unchanged.
        assert "some text" in call_args[1]

    @pytest.mark.asyncio
    async def test_remote_embedding_returns_vector(self):
        vector = [0.1, 0.2]
        mock_remote = AsyncMock(return_value=vector)

        with (
            patch("src.model_services.read_model_config_from_db",
                  return_value={"mode": "remote", "model_name": "text-embedding-3-small"}),
            patch("src.model_services._call_remote_embedding", mock_remote),
        ):
            from src.model_services import call_embedding_model
            result = await call_embedding_model("query text", purpose="search")

        assert result == vector


# ---------------------------------------------------------------------------
# call_translation_model
# ---------------------------------------------------------------------------

class TestCallTranslationModel:
    @pytest.mark.asyncio
    async def test_local_forward_translation(self):
        _set_poll_value(_make_result({"translation": "Привет мир"}))
        fake_task_fn = MagicMock()

        with (
            patch("src.model_services.read_model_config_from_db",
                  return_value={"mode": "local"}),
            patch("src.model_services._wait_result", side_effect=_instant_poll),
            patch("src.queues.translation_queue.call_local_translation_model", fake_task_fn),
        ):
            from src.model_services import call_translation_model
            result = await call_translation_model("Hello world", backward=False)

        assert result == "Привет мир"
        call_args = fake_task_fn.call_args[0]
        assert call_args[1] == "Hello world"
        assert call_args[2] is False

    @pytest.mark.asyncio
    async def test_local_backward_translation(self):
        _set_poll_value(_make_result({"translation": "Hello world"}))
        fake_task_fn = MagicMock()

        with (
            patch("src.model_services.read_model_config_from_db",
                  return_value={"mode": "local"}),
            patch("src.model_services._wait_result", side_effect=_instant_poll),
            patch("src.queues.translation_queue.call_local_translation_model", fake_task_fn),
        ):
            from src.model_services import call_translation_model
            result = await call_translation_model("Привет мир", backward=True)

        assert result == "Hello world"
        call_args = fake_task_fn.call_args[0]
        assert call_args[2] is True

    @pytest.mark.asyncio
    async def test_remote_translation(self):
        mock_remote = AsyncMock(return_value="Bonjour")

        with (
            patch("src.model_services.read_model_config_from_db",
                  return_value={"mode": "remote", "model_name": "gpt-4o-mini"}),
            patch("src.model_services._call_remote_translation", mock_remote),
        ):
            from src.model_services import call_translation_model
            result = await call_translation_model("Hello", backward=False)

        assert result == "Bonjour"
        mock_remote.assert_awaited_once()


# ---------------------------------------------------------------------------
# call_ocr_model
# ---------------------------------------------------------------------------

class TestCallOcrModel:
    @pytest.mark.asyncio
    async def test_local_returns_extracted_text(self):
        _set_poll_value(_make_result({"text": "Invoice #1234"}))
        fake_task_fn = MagicMock()

        with (
            patch("src.model_services.read_model_config_from_db",
                  return_value={"mode": "local"}),
            patch("src.model_services._wait_result", side_effect=_instant_poll),
            patch("src.queues.ocr_queue.call_local_ocr_model", fake_task_fn),
        ):
            from src.model_services import call_ocr_model
            result = await call_ocr_model("/tmp/doc.jpg")

        assert result == "Invoice #1234"
        call_args = fake_task_fn.call_args[0]
        assert call_args[1] == "/tmp/doc.jpg"

    @pytest.mark.asyncio
    async def test_local_empty_text_returns_empty_string(self):
        _set_poll_value(_make_result({"text": ""}))
        fake_task_fn = MagicMock()

        with (
            patch("src.model_services.read_model_config_from_db",
                  return_value={"mode": "local"}),
            patch("src.model_services._wait_result", side_effect=_instant_poll),
            patch("src.queues.ocr_queue.call_local_ocr_model", fake_task_fn),
        ):
            from src.model_services import call_ocr_model
            result = await call_ocr_model("/tmp/photo.jpg")

        assert result == ""

    @pytest.mark.asyncio
    async def test_remote_ocr_returns_text(self):
        mock_remote = AsyncMock(return_value="Hello OCR")

        with (
            patch("src.model_services.read_model_config_from_db",
                  return_value={"mode": "remote", "model_name": "gpt-4o"}),
            patch("src.model_services._call_remote_ocr", mock_remote),
        ):
            from src.model_services import call_ocr_model
            result = await call_ocr_model("/tmp/scan.jpg")

        assert result == "Hello OCR"


# ---------------------------------------------------------------------------
# _wait_result — delegates to TaskResultNotifier
# ---------------------------------------------------------------------------

class TestWaitResult:
    @pytest.mark.asyncio
    async def test_delegates_to_notifier_and_returns_value(self):
        from src.model_services import _wait_result

        mock_notifier = MagicMock()
        mock_notifier.wait_for_result = AsyncMock(return_value='{"ok": true}')

        with patch("src.model_services.get_notifier", return_value=mock_notifier):
            result = await _wait_result("task-123", label="test")

        assert result == '{"ok": true}'
        mock_notifier.wait_for_result.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_propagates_timeout_error(self):
        from src.model_services import _wait_result
        import asyncio

        mock_notifier = MagicMock()
        mock_notifier.wait_for_result = AsyncMock(side_effect=asyncio.TimeoutError())

        with patch("src.model_services.get_notifier", return_value=mock_notifier):
            with pytest.raises(asyncio.TimeoutError):
                await _wait_result("bad-task-id")
