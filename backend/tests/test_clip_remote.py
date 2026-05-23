"""
TDD tests for remote CLIP tagger.

Tests cover:
- RemoteClipTagger.get_tags returns a list of (tag, score) tuples
- RemoteClipTagger parses LLM JSON response correctly
- RemoteClipTagger filters results by threshold
- RemoteClipTagger.get_categories works the same way
- RemoteClipTagger returns empty list on malformed JSON (with warning)
- RemoteClipTagger.encode_image raises NotImplementedError
- call_clip_model routes to local Huey task when mode=local
- call_clip_model routes to remote when mode=remote
"""
import sys
import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

# Earlier test files set src.ai, src.ai.clip_remote, src.model_services, and
# src.queues.* to MagicMocks.  Evict them so the real modules are imported.
for _m in ['src.model_services', 'src.task_notifier',
           'src.ai', 'src.ai.clip_remote',
           'src.queues', 'src.queues.clip_queue', 'src.queues.queue_config']:
    sys.modules.pop(_m, None)

import src.queues.clip_queue  # noqa: pre-import so patch can resolve


SAMPLE_TAGS = [f"tag_{i}" for i in range(20)]
SAMPLE_CATEGORIES = ["Nature", "Urban", "People", "Food", "Sports"]


# ---------------------------------------------------------------------------
# RemoteClipTagger — tag classification
# ---------------------------------------------------------------------------

class TestRemoteClipTaggerGetTags:
    def _make_tagger(self, llm_response: str):
        from src.ai.clip_remote import RemoteClipTagger
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=llm_response)
        return RemoteClipTagger(
            llm=mock_llm,
            all_tags=SAMPLE_TAGS,
            all_categories=SAMPLE_CATEGORIES,
            threshold=0.3,
        )

    def test_returns_list_of_tag_score_tuples(self, tmp_path):
        f = tmp_path / "img.jpg"
        f.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)

        llm_json = json.dumps([
            {"tag": "tag_0", "score": 0.9},
            {"tag": "tag_1", "score": 0.7},
        ])
        tagger = self._make_tagger(llm_json)
        result = tagger.get_tags(str(f))

        assert isinstance(result, list)
        assert all(isinstance(t, tuple) and len(t) == 2 for t in result)
        assert ("tag_0", pytest.approx(0.9)) in result

    def test_filters_below_threshold(self, tmp_path):
        f = tmp_path / "img.jpg"
        f.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)

        llm_json = json.dumps([
            {"tag": "tag_0", "score": 0.9},
            {"tag": "tag_1", "score": 0.1},  # below 0.3 threshold
        ])
        tagger = self._make_tagger(llm_json)
        result = tagger.get_tags(str(f))

        tag_names = [r[0] for r in result]
        assert "tag_0" in tag_names
        assert "tag_1" not in tag_names

    def test_only_returns_known_tags(self, tmp_path):
        f = tmp_path / "img.jpg"
        f.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)

        llm_json = json.dumps([
            {"tag": "tag_0", "score": 0.9},
            {"tag": "unknown_hallucinated_tag", "score": 0.8},
        ])
        tagger = self._make_tagger(llm_json)
        result = tagger.get_tags(str(f))

        tag_names = [r[0] for r in result]
        assert "unknown_hallucinated_tag" not in tag_names

    def test_returns_empty_list_on_malformed_json(self, tmp_path):
        f = tmp_path / "img.jpg"
        f.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)

        tagger = self._make_tagger("not valid json { broken")
        result = tagger.get_tags(str(f))
        assert result == []

    def test_returns_empty_list_on_unexpected_structure(self, tmp_path):
        f = tmp_path / "img.jpg"
        f.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)

        tagger = self._make_tagger(json.dumps({"error": "sorry"}))
        result = tagger.get_tags(str(f))
        assert result == []


class TestRemoteClipTaggerGetCategories:
    def test_get_categories_returns_scored_categories(self, tmp_path):
        from src.ai.clip_remote import RemoteClipTagger
        f = tmp_path / "img.jpg"
        f.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)

        llm_json = json.dumps([{"tag": "Nature", "score": 0.85}])
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=llm_json)
        tagger = RemoteClipTagger(mock_llm, SAMPLE_TAGS, SAMPLE_CATEGORIES, threshold=0.3)

        result = tagger.get_categories(str(f))
        assert any(name == "Nature" for name, _ in result)


class TestRemoteClipTaggerEncodeImage:
    def test_encode_image_raises_not_implemented(self, tmp_path):
        from src.ai.clip_remote import RemoteClipTagger
        f = tmp_path / "img.jpg"
        f.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)

        mock_llm = MagicMock()
        tagger = RemoteClipTagger(mock_llm, SAMPLE_TAGS, SAMPLE_CATEGORIES)
        with pytest.raises(NotImplementedError):
            tagger.encode_image(str(f))


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

class TestRemoteClipTaggerPrompt:
    def test_prompt_contains_candidate_tags(self, tmp_path):
        from src.ai.clip_remote import RemoteClipTagger
        f = tmp_path / "img.jpg"
        f.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="[]")
        tags = ["sunset", "beach", "ocean"]
        tagger = RemoteClipTagger(mock_llm, tags, [], threshold=0.3)
        tagger.get_tags(str(f))

        invoke_call = mock_llm.invoke.call_args[0][0]
        full_text = str(invoke_call)
        assert "sunset" in full_text
        assert "beach" in full_text

    def test_sends_at_most_200_tags(self, tmp_path):
        from src.ai.clip_remote import RemoteClipTagger
        f = tmp_path / "img.jpg"
        f.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="[]")
        many_tags = [f"tag_{i}" for i in range(600)]
        tagger = RemoteClipTagger(mock_llm, many_tags, [], threshold=0.3)
        tagger.get_tags(str(f))

        invoke_call = mock_llm.invoke.call_args[0][0]
        full_text = str(invoke_call)
        # Only first 200 tags should appear in the prompt
        assert "tag_199" in full_text
        assert "tag_200" not in full_text


# ---------------------------------------------------------------------------
# call_clip_model dispatch
# ---------------------------------------------------------------------------

class TestCallClipModelDispatch:
    @pytest.mark.asyncio
    async def test_local_mode_submits_huey_task(self):
        from src.model_services import call_clip_model
        with patch("src.model_services.read_model_config_from_db",
                   return_value={"mode": "local", "model_name": "ViT-B-32"}), \
             patch("src.queues.clip_queue.call_local_clip_model") as mock_task, \
             patch("src.model_services._wait_result", new_callable=AsyncMock,
                   return_value=json.dumps([["cat", 0.8], ["dog", 0.6]])):
            mock_task.return_value = None
            result = await call_clip_model("/fake/img.jpg", task="tags")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_remote_mode_calls_remote_clip(self):
        from src.model_services import call_clip_model
        cfg = {"mode": "remote", "model_name": "gpt-4o",
               "model_provider": "openai", "api_key": "k", "url": None}
        with patch("src.model_services.read_model_config_from_db", return_value=cfg), \
             patch("src.model_services._call_remote_clip",
                   new_callable=AsyncMock,
                   return_value=[["sunset", 0.9]]) as mock_remote:
            result = await call_clip_model("/fake/img.jpg", task="tags")
        assert result == [["sunset", 0.9]]
        mock_remote.assert_called_once()
