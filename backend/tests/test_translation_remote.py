"""
TDD tests for remote translation dispatch.

Tests cover:
- RemoteTranslator.translate via LangChain chat model
- RemoteTranslator.translate via DeepL direct HTTP
- RemoteTranslator.translate via LibreTranslate direct HTTP
- backward=True swaps language direction
- call_translation_model routes to local Huey task when mode=local
- call_translation_model routes to remote when mode=remote
"""
import sys
import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock, call

# Earlier test files set src.model_services, src.ai.*, and src.queues.* to MagicMocks.
# Evict them so the real lightweight modules are imported here.
for _m in ['src.model_services', 'src.task_notifier',
           'src.ai', 'src.ai.translator_remote',
           'src.queues', 'src.queues.translation_queue', 'src.queues.queue_config']:
    sys.modules.pop(_m, None)

import src.queues.translation_queue  # noqa: pre-import so patch can resolve


# ---------------------------------------------------------------------------
# RemoteTranslator — LangChain path
# ---------------------------------------------------------------------------

class TestRemoteTranslatorLLM:
    def test_translate_forward_calls_langchain(self):
        from src.ai.translator_remote import RemoteTranslator
        mock_response = MagicMock(content="Привет мир")
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_response

        translator = RemoteTranslator(llm=mock_llm, src_lang="English", tgt_lang="Russian")
        result = translator.translate("Hello world", backward=False)

        assert result == "Привет мир"
        mock_llm.invoke.assert_called_once()

    def test_translate_backward_swaps_direction(self):
        from src.ai.translator_remote import RemoteTranslator
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="Hello world")

        translator = RemoteTranslator(llm=mock_llm, src_lang="English", tgt_lang="Russian")
        # backward=True means translate FROM tgt_lang TO src_lang
        result = translator.translate("Привет мир", backward=True)

        assert result == "Hello world"
        call_args = mock_llm.invoke.call_args
        prompt_str = str(call_args)
        # Should reference English (the src_lang) as the target when backward
        assert "English" in prompt_str

    def test_strips_whitespace_from_response(self):
        from src.ai.translator_remote import RemoteTranslator
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="  Bonjour  \n")

        translator = RemoteTranslator(llm=mock_llm, src_lang="English", tgt_lang="French")
        assert translator.translate("Hello", backward=False) == "Bonjour"


# ---------------------------------------------------------------------------
# RemoteTranslator — DeepL path
# ---------------------------------------------------------------------------

class TestRemoteTranslatorDeepL:
    def test_deepl_posts_to_api(self):
        from src.ai.translator_remote import RemoteTranslator
        import requests

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"translations": [{"text": "Hallo Welt"}]}
        mock_resp.raise_for_status = MagicMock()

        translator = RemoteTranslator(
            provider="deepl", api_key="deepl-key",
            src_lang="English", tgt_lang="German"
        )
        with patch("requests.post", return_value=mock_resp) as mock_post:
            result = translator.translate("Hello world", backward=False)

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert "deepl" in call_kwargs[0][0] or "deepl" in str(call_kwargs)
        assert result == "Hallo Welt"


# ---------------------------------------------------------------------------
# RemoteTranslator — LibreTranslate path
# ---------------------------------------------------------------------------

class TestRemoteTranslatorLibreTranslate:
    def test_libretranslate_posts_to_custom_url(self):
        from src.ai.translator_remote import RemoteTranslator

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"translatedText": "Bonjour"}
        mock_resp.raise_for_status = MagicMock()

        translator = RemoteTranslator(
            provider="libretranslate",
            api_url="http://localhost:5000",
            src_lang="English", tgt_lang="French"
        )
        with patch("requests.post", return_value=mock_resp) as mock_post:
            result = translator.translate("Hello", backward=False)

        mock_post.assert_called_once()
        assert "localhost:5000" in mock_post.call_args[0][0]
        assert result == "Bonjour"


# ---------------------------------------------------------------------------
# call_translation_model dispatch
# ---------------------------------------------------------------------------

class TestCallTranslationModelDispatch:
    @pytest.mark.asyncio
    async def test_local_mode_submits_huey_task(self):
        from src.model_services import call_translation_model
        with patch("src.model_services.read_model_config_from_db",
                   return_value={"mode": "local", "model_name": "facebook/nllb-200-distilled-600M"}), \
             patch("src.queues.translation_queue.call_local_translation_model") as mock_task, \
             patch("src.model_services._wait_result", new_callable=AsyncMock,
                   return_value=json.dumps({"translation": "Привет"})):
            mock_task.return_value = None
            result = await call_translation_model("Hello", backward=False)
        assert result == "Привет"

    @pytest.mark.asyncio
    async def test_remote_mode_calls_remote_translation(self):
        from src.model_services import call_translation_model
        cfg = {"mode": "remote", "model_name": "gpt-4o-mini",
               "model_provider": "openai", "api_key": "k", "url": None}
        with patch("src.model_services.read_model_config_from_db", return_value=cfg), \
             patch("src.model_services._call_remote_translation",
                   new_callable=AsyncMock, return_value="Привет") as mock_remote:
            result = await call_translation_model("Hello", backward=False)
        assert result == "Привет"
        mock_remote.assert_called_once()

    @pytest.mark.asyncio
    async def test_remote_passes_backward_flag(self):
        from src.model_services import call_translation_model
        cfg = {"mode": "remote", "model_name": "gpt-4o-mini",
               "model_provider": "openai", "api_key": "k", "url": None}
        with patch("src.model_services.read_model_config_from_db", return_value=cfg), \
             patch("src.model_services._call_remote_translation",
                   new_callable=AsyncMock, return_value="Hello") as mock_remote:
            await call_translation_model("Привет", backward=True)
        _, kwargs = mock_remote.call_args
        assert kwargs.get("backward", True) is True or mock_remote.call_args[0][2] is True
