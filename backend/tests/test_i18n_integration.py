"""
Integration tests for the i18n feature — Phase 8.10.

Tests the end-to-end flow:
  - Settings API stores and returns the selected language
  - POST /api/translation/retranslate-all starts the pipeline (when lang != en)
  - POST /api/translation/retranslate-all is a no-op for English
  - Chat AI system prompt includes language instruction for non-English
  - bootstrap.py applies installer language choice only on first launch
"""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import sqlalchemy.types

# --- atomic mocks for heavy deps (must run before any src.* import) ---
mock_pgvector = MagicMock()
mock_pgvector.sqlalchemy.Vector = lambda size: sqlalchemy.types.JSON()
sys.modules.setdefault("pgvector", mock_pgvector)
sys.modules.setdefault("pgvector.sqlalchemy", mock_pgvector.sqlalchemy)

for _mod in [
    "sqlite_vec",
    "langgraph",
    "langgraph.graph",
    "langgraph.prebuilt",
    "langgraph.checkpoint.memory",
    "src.database",
    "src.vector_db_services",
    "src.ai",
    "src.ai.registry",
    "src.ai.prompts",
    "src.ai.translator",
    # NOTE: src.graphs.ai_agent is NOT mocked here so call_model is importable,
    # but state (which needs langgraph.graph.message) must stay mocked since
    # langgraph.graph is mocked above.
    "src.graphs.state",
    "src.queues",
    "src.queues.folder_scan_queue",
    "src.queues.clip_queue",
    "src.queues.vision_queue",
    "src.queues.embedding_queue",
    "src.queues.translation_queue",
    "src.queues.queue_config",
    "src.tasks",
    "src.tasks.utils",
    "src.tasks.folder_scanners",
    "src.tasks.vision_tasks",
    "src.tasks.embedding_tasks",
    "src.tasks.clip_tasks",
    "src.tasks.translation_tasks",
    "src.model_services",
    "src.deps",
    "src.watcher_service",
    "src.watcher",
    "src.incoming_pipeline",
]:
    sys.modules.setdefault(_mod, MagicMock())

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.db_service import get_setting, set_setting
from src.models import Base

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _make_engine():
    """SQLite in-memory engine safe for multi-thread FastAPI test client."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db():
    engine = _make_engine()
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


@pytest.fixture
def client():
    """FastAPI test client with its own in-memory DB shared across requests."""
    engine = _make_engine()
    Session = sessionmaker(bind=engine)

    sys.modules.pop("src.main", None)
    import src.main as main_mod

    def override_db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    deps_mod = sys.modules["src.deps"]
    main_mod.app.dependency_overrides[deps_mod.get_db] = override_db

    from fastapi.testclient import TestClient

    return TestClient(main_mod.app)


# ---------------------------------------------------------------------------
# Settings API round-trip
# ---------------------------------------------------------------------------


class TestSettingsLanguageRoundTrip:
    def test_settings_language_defaults_empty(self, client):
        resp = client.get("/api/settings/")
        assert resp.status_code == 200

    def test_save_and_read_back_russian(self, client):
        client.put("/api/settings/default_language", json={"value": "ru"})
        resp = client.get("/api/settings/")
        assert resp.json().get("default_language") == "ru"

    def test_save_and_read_back_spanish(self, client):
        client.put("/api/settings/default_language", json={"value": "es"})
        resp = client.get("/api/settings/")
        assert resp.json().get("default_language") == "es"


# ---------------------------------------------------------------------------
# Retranslate-all endpoint
# ---------------------------------------------------------------------------


class TestRetranslateAllEndpointIntegration:
    def test_returns_202_for_non_english_language(self, client):
        client.put("/api/settings/default_language", json={"value": "ru"})
        with patch("src.retranslation_pipeline.start_retranslation", new_callable=AsyncMock):
            resp = client.post("/api/translation/retranslate-all")
        assert resp.status_code == 202
        assert resp.json()["status"] == "started"

    def test_returns_202_for_english_without_starting_pipeline(self, client):
        client.put("/api/settings/default_language", json={"value": "en"})
        with patch("src.retranslation_pipeline.start_retranslation", new_callable=AsyncMock) as mock_start:
            resp = client.post("/api/translation/retranslate-all")
        assert resp.status_code == 202
        mock_start.assert_not_called()

    def test_response_includes_language_field(self, client):
        client.put("/api/settings/default_language", json={"value": "es"})
        with patch("src.retranslation_pipeline.start_retranslation", new_callable=AsyncMock):
            resp = client.post("/api/translation/retranslate-all")
        assert resp.json()["language"] == "es"


# ---------------------------------------------------------------------------
# Bootstrap integration: apply_bootstrap_settings + real DB session
# ---------------------------------------------------------------------------


class TestBootstrapSettingsIntegration:
    def test_bootstrap_language_written_to_db(self, tmp_path, db):
        import json

        from src.bootstrap import apply_bootstrap_settings

        (tmp_path / "bootstrap.json").write_text(json.dumps({"default_language": "ru"}))
        with patch("src.bootstrap._bootstrap_path", return_value=tmp_path / "bootstrap.json"):
            apply_bootstrap_settings(db)

        assert get_setting(db, "default_language") == "ru"

    def test_bootstrap_does_not_overwrite_existing_setting(self, tmp_path, db):
        import json

        from src.bootstrap import apply_bootstrap_settings

        set_setting(db, "default_language", "en")
        (tmp_path / "bootstrap.json").write_text(json.dumps({"default_language": "ru"}))
        with patch("src.bootstrap._bootstrap_path", return_value=tmp_path / "bootstrap.json"):
            apply_bootstrap_settings(db)

        assert get_setting(db, "default_language") == "en"

    def test_bootstrap_file_removed_after_apply(self, tmp_path, db):
        import json

        from src.bootstrap import apply_bootstrap_settings

        path = tmp_path / "bootstrap.json"
        path.write_text(json.dumps({"default_language": "es"}))
        with patch("src.bootstrap._bootstrap_path", return_value=path):
            apply_bootstrap_settings(db)

        assert not path.exists()


# ---------------------------------------------------------------------------
# Chat AI language injection integration
# ---------------------------------------------------------------------------


class TestChatLanguageInjectionIntegration:
    """
    Verify call_model injects the correct language instruction.
    src.graphs.ai_agent is NOT in the module-level mock list so the real
    function is importable; only its heavy dependencies are patched inline.
    """

    def _run_call_model(self, language: str) -> str:
        """Run call_model and return the system message content sent to the LLM."""
        # Clear cached import so we get the real module on each run
        sys.modules.pop("src.graphs.ai_agent", None)

        from langchain_core.messages import HumanMessage, SystemMessage

        mock_resp = MagicMock()
        mock_resp.content = "reply"
        mock_registry = MagicMock()
        mock_registry.chat_model.bind_tools.return_value.invoke.return_value = mock_resp

        state = {"messages": [HumanMessage(content="Hello")]}

        with (
            patch("src.graphs.ai_agent.get_prompt", return_value="Base prompt"),
            patch("src.graphs.ai_agent._get_ui_language", return_value=language),
            patch("src.ai.registry.registry", mock_registry),
        ):
            from src.graphs.ai_agent import call_model

            call_model(state)

        llm = mock_registry.chat_model.bind_tools.return_value
        messages = llm.invoke.call_args[0][0]
        system_msgs = [m for m in messages if isinstance(m, SystemMessage)]
        assert system_msgs, "No SystemMessage found in LLM call"
        return system_msgs[0].content

    def test_russian_instruction_injected(self):
        content = self._run_call_model("ru")
        assert "Отвечай на русском языке." in content
        assert "Base prompt" in content

    def test_spanish_instruction_injected(self):
        content = self._run_call_model("es")
        assert "Responde en español." in content

    def test_no_language_instruction_for_english(self):
        content = self._run_call_model("en")
        assert "Отвечай" not in content
        assert "Responde" not in content
