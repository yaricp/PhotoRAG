"""
TDD API tests for photo-edit endpoints:
  PUT  /api/photos/{id}
  PUT  /api/photos/{id}/flags
  POST /api/photos/{id}/tags
  DELETE /api/photos/{id}/tags/{tag_id}
  POST /api/photos/{id}/categories
  DELETE /api/photos/{id}/categories/{cat_id}

Also verifies GET /api/photos/{id} returns is_trash field.
Embedding recompute task is mocked — we only verify it's called.
"""
import sys
from unittest.mock import MagicMock, patch
import sqlalchemy.types

mock_pgvector = MagicMock()
mock_pgvector.sqlalchemy.Vector = lambda size: sqlalchemy.types.JSON()
sys.modules['pgvector'] = mock_pgvector
sys.modules['pgvector.sqlalchemy'] = mock_pgvector.sqlalchemy

for _mod in [
    'sqlite_vec', 'langgraph', 'langgraph.graph',
    'src.database', 'src.vector_db_services',
    'src.ai', 'src.ai.registry', 'src.ai.prompts', 'src.ai.translator',
    'src.graphs.ai_agent',
    'src.queues', 'src.queues.folder_scan_queue', 'src.queues.clip_queue',
    'src.queues.vision_queue', 'src.queues.embedding_queue',
    'src.queues.translation_queue',
    'src.tasks', 'src.tasks.utils', 'src.tasks.folder_scanners',
    'src.tasks.vision_tasks', 'src.tasks.embedding_tasks',
    'src.tasks.clip_tasks', 'src.tasks.translation_tasks',
    'src.tasks.recompute_tasks',
    'src.deps',
]:
    sys.modules[_mod] = MagicMock()

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from src.models import Base, Photo, PhotoQualityIssue, Tag, Category
from src.main import app
from src.deps import get_db

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Base.metadata.create_all(engine)
TestSession = sessionmaker(bind=engine)

EMBEDDING_TASK = "src.tasks.embedding_tasks.final_embedding_task"


@pytest.fixture(autouse=True)
def override_db():
    def _get_test_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.clear()
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def photo():
    db = TestSession()
    p = Photo(file_path="/test/img.jpg", description="original desc")
    db.add(p)
    db.commit()
    db.refresh(p)
    photo_id = p.id
    db.close()
    return photo_id


# ── GET /api/photos/{id} — is_trash field ────────────────────────────────────

class TestGetPhotoIsTrash:
    def test_is_trash_false_by_default(self, client, photo):
        r = client.get(f"/api/photos/{photo}")
        assert r.status_code == 200
        assert r.json()["is_trash"] is False

    def test_is_trash_true_after_marking(self, client, photo):
        db = TestSession()
        db.add(PhotoQualityIssue(photo_id=photo, issue_type="user_trash"))
        db.commit()
        db.close()
        r = client.get(f"/api/photos/{photo}")
        assert r.status_code == 200
        assert r.json()["is_trash"] is True


# ── PUT /api/photos/{id} ──────────────────────────────────────────────────────

class TestUpdatePhoto:
    def test_update_description_returns_200(self, client, photo):
        with patch(EMBEDDING_TASK):
            r = client.put(f"/api/photos/{photo}", json={"description": "new desc"})
        assert r.status_code == 200
        assert r.json()["description"] == "new desc"

    def test_update_ocr_text(self, client, photo):
        with patch(EMBEDDING_TASK):
            r = client.put(f"/api/photos/{photo}", json={"ocr_text": "some text"})
        assert r.status_code == 200
        assert r.json()["ocr_text"] == "some text"

    def test_update_nonexistent_returns_404(self, client):
        with patch(EMBEDDING_TASK):
            r = client.put("/api/photos/9999", json={"description": "x"})
        assert r.status_code == 404

    def test_description_change_triggers_embedding(self, client, photo):
        with patch(EMBEDDING_TASK) as mock_task:
            client.put(f"/api/photos/{photo}", json={"description": "changed"})
        mock_task.assert_called_once_with(photo, phase="edit")

    def test_no_description_change_does_not_trigger_embedding(self, client, photo):
        with patch(EMBEDDING_TASK) as mock_task:
            client.put(f"/api/photos/{photo}", json={"ocr_text": "text only"})
        mock_task.assert_not_called()


# ── PUT /api/photos/{id}/flags ────────────────────────────────────────────────

class TestUpdatePhotoFlags:
    def test_set_is_doc_true(self, client, photo):
        r = client.put(f"/api/photos/{photo}/flags", json={"is_doc": True})
        assert r.status_code == 200
        assert r.json()["is_doc"] is True

    def test_set_is_doc_false(self, client, photo):
        client.put(f"/api/photos/{photo}/flags", json={"is_doc": True})
        r = client.put(f"/api/photos/{photo}/flags", json={"is_doc": False})
        assert r.status_code == 200
        assert r.json()["is_doc"] is False

    def test_set_is_trash_true(self, client, photo):
        r = client.put(f"/api/photos/{photo}/flags", json={"is_trash": True})
        assert r.status_code == 200
        assert r.json()["is_trash"] is True

    def test_set_is_trash_false(self, client, photo):
        client.put(f"/api/photos/{photo}/flags", json={"is_trash": True})
        r = client.put(f"/api/photos/{photo}/flags", json={"is_trash": False})
        assert r.status_code == 200
        assert r.json()["is_trash"] is False

    def test_flags_nonexistent_photo_returns_404(self, client):
        r = client.put("/api/photos/9999/flags", json={"is_doc": True})
        assert r.status_code == 404


# ── POST /api/photos/{id}/tags ────────────────────────────────────────────────

class TestLinkPhotoTag:
    def test_link_tag_returns_201(self, client, photo):
        r = client.post(f"/api/photos/{photo}/tags", json={"name": "sunset"})
        assert r.status_code == 201
        body = r.json()
        assert body["name"] == "sunset"
        assert body["confidence_score"] == 1.0

    def test_link_tag_nonexistent_photo_returns_404(self, client):
        r = client.post("/api/photos/9999/tags", json={"name": "x"})
        assert r.status_code == 404

    def test_link_tag_idempotent(self, client, photo):
        client.post(f"/api/photos/{photo}/tags", json={"name": "mountain"})
        r = client.post(f"/api/photos/{photo}/tags", json={"name": "mountain"})
        assert r.status_code == 201


# ── DELETE /api/photos/{id}/tags/{tag_id} ─────────────────────────────────────

class TestUnlinkPhotoTag:
    def test_unlink_tag_returns_204(self, client, photo):
        r = client.post(f"/api/photos/{photo}/tags", json={"name": "river"})
        tag_id = r.json()["id"]
        r2 = client.delete(f"/api/photos/{photo}/tags/{tag_id}")
        assert r2.status_code == 204

    def test_unlink_tag_not_linked_returns_404(self, client, photo):
        r = client.delete(f"/api/photos/{photo}/tags/9999")
        assert r.status_code == 404


# ── POST /api/photos/{id}/categories ─────────────────────────────────────────

class TestLinkPhotoCategory:
    def test_link_category_returns_201(self, client, photo):
        r = client.post(f"/api/photos/{photo}/categories", json={"name": "nature"})
        assert r.status_code == 201
        body = r.json()
        assert body["name"] == "nature"
        assert body["confidence_score"] == 1.0

    def test_link_category_nonexistent_photo_returns_404(self, client):
        r = client.post("/api/photos/9999/categories", json={"name": "x"})
        assert r.status_code == 404


# ── DELETE /api/photos/{id}/categories/{cat_id} ───────────────────────────────

class TestUnlinkPhotoCategory:
    def test_unlink_category_returns_204(self, client, photo):
        r = client.post(f"/api/photos/{photo}/categories", json={"name": "food"})
        cat_id = r.json()["id"]
        r2 = client.delete(f"/api/photos/{photo}/categories/{cat_id}")
        assert r2.status_code == 204

    def test_unlink_category_not_linked_returns_404(self, client, photo):
        r = client.delete(f"/api/photos/{photo}/categories/9999")
        assert r.status_code == 404
