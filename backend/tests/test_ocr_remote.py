"""
TDD tests for remote OCR dispatch.

Tests cover:
- RemoteOCR.extract_text sends image + OCR prompt and returns text
- RemoteOCR.extract_text strips whitespace from response
- call_ocr_model routes to local Huey task when mode=local
- call_ocr_model routes to remote when mode=remote
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# RemoteOCR
# ---------------------------------------------------------------------------


class TestRemoteOCR:
    def test_returns_text_from_llm(self, tmp_path):
        from src.ai.ocr_remote import RemoteOCR

        f = tmp_path / "doc.jpg"
        f.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)

        mock_response = MagicMock(content="  Hello World  ")
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_response

        ocr = RemoteOCR(mock_llm)
        result = ocr.extract_text(str(f))
        assert result == "Hello World"

    def test_returns_empty_string_when_no_text(self, tmp_path):
        from src.ai.ocr_remote import RemoteOCR

        f = tmp_path / "blank.jpg"
        f.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="")

        ocr = RemoteOCR(mock_llm)
        assert ocr.extract_text(str(f)) == ""

    def test_sends_ocr_prompt_in_message(self, tmp_path):
        from langchain_core.messages import HumanMessage

        from src.ai.ocr_remote import OCR_PROMPT, RemoteOCR

        f = tmp_path / "doc.jpg"
        f.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="text")

        ocr = RemoteOCR(mock_llm)
        ocr.extract_text(str(f))

        call_args = mock_llm.invoke.call_args[0][0]
        msg = call_args[0]
        assert isinstance(msg, HumanMessage)
        text_parts = [c for c in msg.content if c.get("type") == "text"]
        assert any(OCR_PROMPT[:30] in p["text"] for p in text_parts)


# ---------------------------------------------------------------------------
# call_ocr_model dispatch
# ---------------------------------------------------------------------------


class TestCallOcrModelDispatch:
    @pytest.mark.asyncio
    async def test_local_mode_submits_huey_task(self):
        from src.model_services import call_ocr_model

        with (
            patch(
                "src.model_services.read_model_config_from_db", return_value={"mode": "local", "model_name": "easyocr"}
            ),
            patch("src.queues.ocr_queue.call_local_ocr_model") as mock_task,
            patch(
                "src.model_services._wait_result", new_callable=AsyncMock, return_value=json.dumps({"text": "HELLO"})
            ),
        ):
            mock_task.return_value = None
            result = await call_ocr_model("/fake/image.jpg")
        assert result == "HELLO"

    @pytest.mark.asyncio
    async def test_remote_mode_calls_remote_ocr(self):
        from src.model_services import call_ocr_model

        cfg = {"mode": "remote", "model_name": "gpt-4o", "model_provider": "openai", "api_key": "k", "url": None}
        with (
            patch("src.model_services.read_model_config_from_db", return_value=cfg),
            patch(
                "src.model_services._call_remote_ocr", new_callable=AsyncMock, return_value="extracted text"
            ) as mock_remote,
        ):
            result = await call_ocr_model("/fake/image.jpg")
        assert result == "extracted text"
        mock_remote.assert_called_once()
