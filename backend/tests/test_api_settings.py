# backend/tests/test_api_settings.py
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
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.db_service import get_all_settings, set_setting
from src.models import AppSetting, Base


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def client():
    sys.modules.pop("src.main", None)
    import src.main as main_mod

    def override_get_db():
        yield MagicMock()

    main_mod.app.dependency_overrides[sys.modules["src.deps"].get_db] = override_get_db
    from fastapi.testclient import TestClient

    return TestClient(main_mod.app)


def test_get_settings_returns_empty_dict_initially(db):
    result = get_all_settings(db)
    assert result == {}


def test_set_setting_creates_and_updates_value(db):
    setting = set_setting(db, "default_folder", "/photos")
    assert setting.key == "default_folder"
    assert setting.value == "/photos"

    updated = set_setting(db, "default_folder", "/new_photos")
    assert updated.value == "/new_photos"

    # Only one row should exist
    rows = db.query(AppSetting).filter(AppSetting.key == "default_folder").all()
    assert len(rows) == 1


def test_api_get_settings_returns_200(client):
    with patch("src.main.get_all_settings", return_value={"default_folder": ""}):
        resp = client.get("/api/settings/")
    assert resp.status_code == 200
    assert "default_folder" in resp.json()


def test_api_put_setting_updates_value(client):
    mock_setting = MagicMock()
    mock_setting.key = "default_folder"
    mock_setting.value = "/my/photos"
    with patch("src.main.set_setting", return_value=mock_setting):
        resp = client.put("/api/settings/default_folder", json={"value": "/my/photos"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["key"] == "default_folder"
    assert data["value"] == "/my/photos"
