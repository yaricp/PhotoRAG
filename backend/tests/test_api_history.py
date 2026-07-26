# backend/tests/test_api_history.py
import json
import sys
import zipfile
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

from src.db_service import (
    create_history_action,
    get_history_actions,
    get_last_history_action,
    perform_undo,
)
from src.models import Base
from src.models import Photo as PhotoModel


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


def test_create_history_action_persists(db):
    action = create_history_action(
        db,
        action_type="create_folder",
        photo_ids=None,
        params={"path": "/photos/new"},
        undo_data={"path": "/photos/new"},
    )
    assert action.id is not None
    assert action.action_type == "create_folder"
    assert json.loads(action.params)["path"] == "/photos/new"


def test_get_history_actions_returns_list(db):
    create_history_action(db, "create_folder", None, {"path": "/a"}, {"path": "/a"})
    create_history_action(db, "create_folder", None, {"path": "/b"}, {"path": "/b"})
    actions = get_history_actions(db)
    assert len(actions) == 2


def test_get_last_history_action(db):
    create_history_action(db, "create_folder", None, {"path": "/a"}, {"path": "/a"})
    create_history_action(db, "move_photos", [1, 2], {"dest": "/b"}, {"original_paths": {"1": "/a/1.jpg"}})
    last = get_last_history_action(db)
    assert last.action_type == "move_photos"


def test_undo_create_folder_removes_directory(db, tmp_path):
    folder = tmp_path / "test_new_folder"
    folder.mkdir()
    create_history_action(
        db,
        "create_folder",
        None,
        {"path": str(folder)},
        {"path": str(folder)},
    )
    result = perform_undo(db)
    assert "create_folder" in result
    assert not folder.exists()


def test_undo_move_photos_restores_paths(db, tmp_path):
    # Create a source photo file
    src_file = tmp_path / "moved.jpg"
    src_file.write_bytes(b"img")
    original_path = str(tmp_path / "original.jpg")

    # Add photo record pointing to moved location
    photo = PhotoModel(hash="abc123", file_path=str(src_file))
    db.add(photo)
    db.commit()
    db.refresh(photo)

    create_history_action(
        db,
        "move_photos",
        [photo.id],
        {"destination": str(tmp_path)},
        {"original_paths": {str(photo.id): original_path}},
    )
    result = perform_undo(db)
    assert "move_photos" in result
    db.refresh(photo)
    assert photo.file_path == original_path


def test_undo_archive_photos_deletes_zip(db, tmp_path):
    zip_path = tmp_path / "MyPhotoArchive.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("photo1.jpg", b"data")

    create_history_action(
        db,
        "archive_photos",
        [1],
        {"zip_path": str(zip_path)},
        {"zip_path": str(zip_path), "added_names": ["photo1.jpg"], "newly_archived_ids": []},
    )
    result = perform_undo(db)
    assert "archive_photos" in result
    assert not zip_path.exists()


def test_undo_returns_error_when_no_history(db):
    result = perform_undo(db)
    assert "No action" in result


def test_api_get_history_returns_200(client):
    with patch("src.main.get_history_actions", return_value=[]):
        resp = client.get("/api/history/")
    assert resp.status_code == 200
    assert resp.json() == []


def test_api_history_undo_returns_ok(client):
    with patch("src.main.perform_undo", return_value="Undone: create_folder"):
        resp = client.post("/api/history/undo/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "create_folder" in data["detail"]
