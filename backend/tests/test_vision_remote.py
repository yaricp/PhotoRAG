"""
TDD tests for remote vision dispatch.

Tests cover:
- _encode_image_base64 returns a base64 string
- _build_langchain_vision_model returns the correct LangChain class per provider
- _call_remote_vision sends image + prompt and returns text
- call_vision_model routes to local Huey task when mode=local
- call_vision_model routes to remote when mode=remote
"""

import base64
import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Earlier test files set src.model_services, src.queues.*, and src.queues.queue_config
# to MagicMocks.  Evict them so we always import the real lightweight modules here.
for _m in [
    "src.model_services",
    "src.task_notifier",
    "src.queues",
    "src.queues.vision_queue",
    "src.queues.queue_config",
]:
    sys.modules.pop(_m, None)


# ---------------------------------------------------------------------------
# _encode_image_base64
# ---------------------------------------------------------------------------


class TestEncodeImageBase64:
    def test_returns_base64_string_for_valid_image(self, tmp_path):
        from src.model_services import _encode_image_base64

        f = tmp_path / "test.jpg"
        f.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)
        result = _encode_image_base64(str(f))
        assert isinstance(result, str)
        decoded = base64.b64decode(result)
        assert decoded[:4] == b"\xff\xd8\xff\xe0"

    def test_raises_for_missing_file(self):
        from src.model_services import _encode_image_base64

        with pytest.raises(FileNotFoundError):
            _encode_image_base64("/nonexistent/image.jpg")


# ---------------------------------------------------------------------------
# _build_langchain_vision_model
# ---------------------------------------------------------------------------


class TestBuildLangchainVisionModel:
    def test_openai_provider_returns_chat_openai(self):
        from src.model_services import _build_langchain_vision_model

        mock_cls = MagicMock()
        with patch.dict("sys.modules", {"langchain_openai": MagicMock(ChatOpenAI=mock_cls)}):
            _build_langchain_vision_model("openai", "gpt-4o", "sk-test", None)
            mock_cls.assert_called_once()

    def test_anthropic_provider_returns_chat_anthropic(self):
        from src.model_services import _build_langchain_vision_model

        mock_cls = MagicMock()
        with patch.dict("sys.modules", {"langchain_anthropic": MagicMock(ChatAnthropic=mock_cls)}):
            _build_langchain_vision_model("anthropic", "claude-3-haiku-20240307", "sk-ant", None)
            mock_cls.assert_called_once()

    def test_google_genai_provider_returns_chat_google(self):
        from src.model_services import _build_langchain_vision_model

        mock_cls = MagicMock()
        with patch.dict("sys.modules", {"langchain_google_genai": MagicMock(ChatGoogleGenerativeAI=mock_cls)}):
            _build_langchain_vision_model("google_genai", "gemini-1.5-flash", "key", None)
            mock_cls.assert_called_once()

    def test_ollama_provider_returns_chat_ollama(self):
        from src.model_services import _build_langchain_vision_model

        mock_cls = MagicMock()
        with patch.dict("sys.modules", {"langchain_ollama": MagicMock(ChatOllama=mock_cls)}):
            _build_langchain_vision_model("ollama", "llava", None, "http://localhost:11434")
            mock_cls.assert_called_once()

    def test_default_unknown_provider_uses_openai(self):
        from src.model_services import _build_langchain_vision_model

        mock_cls = MagicMock()
        with patch.dict("sys.modules", {"langchain_openai": MagicMock(ChatOpenAI=mock_cls)}):
            _build_langchain_vision_model(None, "gpt-4o", "key", None)
            mock_cls.assert_called_once()


# ---------------------------------------------------------------------------
# _call_remote_vision
# ---------------------------------------------------------------------------


class TestCallRemoteVision:
    def test_returns_content_from_llm_response(self, tmp_path):
        from src.model_services import _call_remote_vision

        f = tmp_path / "photo.jpg"
        f.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)

        mock_response = MagicMock()
        mock_response.content = "A sunny beach scene."
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_response

        cfg = {"model_provider": "openai", "model_name": "gpt-4o", "api_key": "k", "url": None}
        with patch("src.model_services._build_langchain_vision_model", return_value=mock_llm):
            import asyncio

            result = asyncio.get_event_loop().run_until_complete(
                _call_remote_vision(cfg, str(f), "Describe this image.")
            )
        assert result == "A sunny beach scene."

    def test_passes_base64_image_in_message(self, tmp_path):
        from langchain_core.messages import HumanMessage

        from src.model_services import _call_remote_vision

        f = tmp_path / "photo.jpg"
        f.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)

        mock_response = MagicMock(content="ok")
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_response

        cfg = {"model_provider": "openai", "model_name": "gpt-4o", "api_key": "k", "url": None}
        with patch("src.model_services._build_langchain_vision_model", return_value=mock_llm):
            import asyncio

            asyncio.get_event_loop().run_until_complete(_call_remote_vision(cfg, str(f), "describe"))

        call_args = mock_llm.invoke.call_args[0][0]
        assert len(call_args) == 1
        msg = call_args[0]
        assert isinstance(msg, HumanMessage)
        content_types = [c["type"] for c in msg.content]
        assert "image_url" in content_types
        assert "text" in content_types


# ---------------------------------------------------------------------------
# call_vision_model integration
# ---------------------------------------------------------------------------


class TestCallVisionModelDispatch:
    @pytest.mark.asyncio
    async def test_local_mode_submits_huey_task(self):
        from src.model_services import call_vision_model

        with (
            patch(
                "src.model_services.read_model_config_from_db",
                return_value={"mode": "local", "model_name": "Qwen/Qwen2-VL-2B-Instruct"},
            ),
            patch("src.queues.vision_queue.call_local_vision_model") as mock_task,
            patch(
                "src.model_services._wait_result", new_callable=AsyncMock, return_value=json.dumps({"text": "a cat"})
            ),
        ):
            mock_task.return_value = None
            result = await call_vision_model("/fake/path.jpg", "describe_scene")
        assert result == "a cat"

    @pytest.mark.asyncio
    async def test_remote_mode_calls_remote_vision(self):
        from src.model_services import call_vision_model

        cfg = {"mode": "remote", "model_name": "gpt-4o", "model_provider": "openai", "api_key": "k", "url": None}
        with (
            patch("src.model_services.read_model_config_from_db", return_value=cfg),
            patch(
                "src.model_services._call_remote_vision", new_callable=AsyncMock, return_value="beach"
            ) as mock_remote,
        ):
            result = await call_vision_model("/fake/path.jpg", "describe_scene")
        assert result == "beach"
        mock_remote.assert_called_once()
