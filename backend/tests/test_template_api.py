"""
TDD API tests for /api/template-tags/ and /api/template-categories/ endpoints.
Recompute trigger is mocked — we verify it's called, not that it actually runs.
"""

import sys
from unittest.mock import MagicMock, patch

import sqlalchemy.types

mock_pgvector = MagicMock()
mock_pgvector.sqlalchemy.Vector = lambda size: sqlalchemy.types.JSON()
sys.modules.setdefault("pgvector", mock_pgvector)
sys.modules.setdefault("pgvector.sqlalchemy", mock_pgvector.sqlalchemy)

for _mod in [
    "sqlite_vec",
    "langgraph",
    "langgraph.graph",
    "src.database",
    "src.vector_db_services",
    "src.ai",
    "src.ai.registry",
    "src.ai.prompts",
    "src.ai.translator",
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
    "src.tasks.recompute_tasks",
    "src.model_services",
    "src.watcher_service",
    "src.task_notifier",
    "src.deps",
]:
    sys.modules.setdefault(_mod, MagicMock())

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.deps import get_db
from src.main import app
from src.models import Base

# StaticPool ensures all sessions share the same in-memory SQLite connection
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Base.metadata.create_all(engine)
TestSession = sessionmaker(bind=engine)


@pytest.fixture(autouse=True)
def override_db():
    """Replace get_db dependency with test SQLite session."""

    def _get_test_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.clear()
    # Wipe all rows between tests
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture
def client():
    return TestClient(app)


RECOMPUTE_TAGS = "src.tasks.recompute_tasks.trigger_recompute_tags"
RECOMPUTE_CATS = "src.tasks.recompute_tasks.trigger_recompute_categories"


# ── Template Tags ─────────────────────────────────────────────────────────────


class TestListTemplateTags:
    def test_empty_list(self, client):
        r = client.get("/api/template-tags/")
        assert r.status_code == 200
        body = r.json()
        assert body["items"] == []
        assert body["total"] == 0

    def test_pagination(self, client):
        for i in range(10):
            client.post("/api/template-tags/", json={"name": f"tag_{i:02d}", "clip_prompt": f"tag {i}"})
        r = client.get("/api/template-tags/?skip=0&limit=5")
        assert r.status_code == 200
        body = r.json()
        assert len(body["items"]) == 5
        assert body["total"] == 10


class TestCreateTemplateTag:
    def test_returns_201_with_data(self, client):
        with patch(RECOMPUTE_TAGS):
            r = client.post("/api/template-tags/", json={"name": "dog", "clip_prompt": "a photo of a dog"})
        assert r.status_code == 201
        body = r.json()
        assert body["name"] == "dog"
        assert body["clip_prompt"] == "a photo of a dog"
        assert "id" in body

    def test_duplicate_name_returns_409(self, client):
        with patch(RECOMPUTE_TAGS):
            client.post("/api/template-tags/", json={"name": "cat", "clip_prompt": "cat"})
            r = client.post("/api/template-tags/", json={"name": "cat", "clip_prompt": "cat again"})
        assert r.status_code == 409

    def test_triggers_recompute(self, client):
        with patch(RECOMPUTE_TAGS) as mock_recompute:
            client.post("/api/template-tags/", json={"name": "bird", "clip_prompt": "bird"})
        mock_recompute.assert_called_once()

    def test_missing_fields_returns_422(self, client):
        r = client.post("/api/template-tags/", json={"name": "only_name"})
        assert r.status_code == 422


class TestUpdateTemplateTag:
    def test_update_name_and_prompt(self, client):
        with patch(RECOMPUTE_TAGS):
            created = client.post("/api/template-tags/", json={"name": "old", "clip_prompt": "old"}).json()
            r = client.put(f"/api/template-tags/{created['id']}", json={"name": "new", "clip_prompt": "new prompt"})
        assert r.status_code == 200
        assert r.json()["name"] == "new"
        assert r.json()["clip_prompt"] == "new prompt"

    def test_update_nonexistent_returns_404(self, client):
        with patch(RECOMPUTE_TAGS):
            r = client.put("/api/template-tags/9999", json={"name": "x", "clip_prompt": "x"})
        assert r.status_code == 404

    def test_update_triggers_recompute(self, client):
        with patch(RECOMPUTE_TAGS) as mock_recompute:
            created = client.post("/api/template-tags/", json={"name": "trig", "clip_prompt": "trig"}).json()
            client.put(f"/api/template-tags/{created['id']}", json={"name": "trig2", "clip_prompt": "trig2"})
        assert mock_recompute.call_count == 2


class TestDeleteTemplateTag:
    def test_delete_existing_returns_204(self, client):
        with patch(RECOMPUTE_TAGS):
            created = client.post("/api/template-tags/", json={"name": "del", "clip_prompt": "del"}).json()
            r = client.delete(f"/api/template-tags/{created['id']}")
        assert r.status_code == 204

    def test_delete_nonexistent_returns_404(self, client):
        with patch(RECOMPUTE_TAGS):
            r = client.delete("/api/template-tags/9999")
        assert r.status_code == 404

    def test_delete_triggers_recompute(self, client):
        with patch(RECOMPUTE_TAGS) as mock_recompute:
            created = client.post("/api/template-tags/", json={"name": "del2", "clip_prompt": "del2"}).json()
            client.delete(f"/api/template-tags/{created['id']}")
        assert mock_recompute.call_count == 2


# ── Template Categories ───────────────────────────────────────────────────────


class TestListTemplateCategories:
    def test_empty_list(self, client):
        r = client.get("/api/template-categories/")
        assert r.status_code == 200
        assert r.json()["items"] == []

    def test_pagination(self, client):
        for i in range(8):
            client.post("/api/template-categories/", json={"name": f"cat_{i}", "clip_prompt": f"cat {i}"})
        r = client.get("/api/template-categories/?skip=0&limit=3")
        assert len(r.json()["items"]) == 3
        assert r.json()["total"] == 8


class TestCreateTemplateCategory:
    def test_create(self, client):
        with patch(RECOMPUTE_CATS):
            r = client.post("/api/template-categories/", json={"name": "food", "clip_prompt": "a photo of food"})
        assert r.status_code == 201
        assert r.json()["name"] == "food"

    def test_duplicate_returns_409(self, client):
        with patch(RECOMPUTE_CATS):
            client.post("/api/template-categories/", json={"name": "travel", "clip_prompt": "travel"})
            r = client.post("/api/template-categories/", json={"name": "travel", "clip_prompt": "travel2"})
        assert r.status_code == 409

    def test_triggers_recompute(self, client):
        with patch(RECOMPUTE_CATS) as mock_recompute:
            client.post("/api/template-categories/", json={"name": "sport", "clip_prompt": "sport"})
        mock_recompute.assert_called_once()


class TestUpdateTemplateCategory:
    def test_update(self, client):
        with patch(RECOMPUTE_CATS):
            created = client.post("/api/template-categories/", json={"name": "old_c", "clip_prompt": "old"}).json()
            r = client.put(f"/api/template-categories/{created['id']}", json={"name": "new_c", "clip_prompt": "new"})
        assert r.status_code == 200
        assert r.json()["name"] == "new_c"

    def test_update_nonexistent_404(self, client):
        with patch(RECOMPUTE_CATS):
            r = client.put("/api/template-categories/9999", json={"name": "x", "clip_prompt": "x"})
        assert r.status_code == 404


class TestDeleteTemplateCategory:
    def test_delete(self, client):
        with patch(RECOMPUTE_CATS):
            created = client.post("/api/template-categories/", json={"name": "del_c", "clip_prompt": "del"}).json()
            r = client.delete(f"/api/template-categories/{created['id']}")
        assert r.status_code == 204

    def test_delete_nonexistent_404(self, client):
        r = client.delete("/api/template-categories/9999")
        assert r.status_code == 404
