# backend/tests/test_api_garbage.py
import sys
from unittest.mock import MagicMock, patch

import sqlalchemy.types

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
    "src.model_services",
    "src.watcher_service",
    "src.task_notifier",
    "src.deps",
]:
    sys.modules.setdefault(_mod, MagicMock())

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    sys.modules.pop("src.main", None)
    import src.main as main_mod

    # Override get_db dependency so FastAPI can resolve it without a real DB
    def override_get_db():
        yield MagicMock()

    main_mod.app.dependency_overrides[sys.modules["src.deps"].get_db] = override_get_db
    return TestClient(main_mod.app)


def test_get_garbage_summary_empty(client):
    with patch("src.main.get_quality_summary", return_value={}):
        resp = client.get("/api/garbage/")
    assert resp.status_code == 200
    assert resp.json() == {"counts": {}}


def test_get_garbage_summary_with_data(client):
    with patch("src.main.get_quality_summary", return_value={"blur": 3, "no_exif": 7}):
        resp = client.get("/api/garbage/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["counts"]["blur"] == 3
    assert data["counts"]["no_exif"] == 7


def test_get_garbage_photos_returns_paginated(client):
    mock_photo = MagicMock()
    mock_photo.id = 1
    mock_photo.file_path = "/tmp/a.jpg"
    mock_photo.hash = "abc"
    mock_photo.description = None
    mock_photo.is_doc = False
    mock_photo.ocr_text = None
    mock_photo.created_at = None
    mock_photo.captured_at = None
    mock_photo.file_created_at = None
    mock_photo.translated_description = None
    mock_photo.tags_rel = []
    mock_photo.categories_rel = []
    mock_photo.camera = None
    mock_photo.geoposition = None
    mock_photo.image_width = None
    mock_photo.image_height = None
    mock_photo.iso = None
    mock_photo.aperture = None
    mock_photo.focal_length = None
    mock_photo.shutter_speed = None
    mock_photo.offset_time = None
    mock_photo.is_archived = False

    with patch("src.main.get_photos_by_issue_type", return_value=([mock_photo], 1)):
        resp = client.get("/api/garbage/blur/photos/?skip=0&limit=20")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1


def test_get_garbage_photos_unknown_type_returns_empty(client):
    with patch("src.main.get_photos_by_issue_type", return_value=([], 0)):
        resp = client.get("/api/garbage/nonexistent/photos/")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0
