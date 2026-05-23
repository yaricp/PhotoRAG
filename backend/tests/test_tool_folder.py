# backend/tests/test_tool_folder.py
import sys
import json
from unittest.mock import MagicMock, patch
import sqlalchemy.types

mock_pgvector = MagicMock()
mock_pgvector.sqlalchemy.Vector = lambda size: sqlalchemy.types.JSON()
sys.modules.setdefault('pgvector', mock_pgvector)
sys.modules.setdefault('pgvector.sqlalchemy', mock_pgvector.sqlalchemy)

for _mod in [
    'sqlite_vec', 'langgraph', 'langgraph.graph',
    'src.database', 'src.vector_db_services',
    'src.ai', 'src.ai.registry', 'src.ai.prompts', 'src.ai.translator',
    'src.queues', 'src.queues.folder_scan_queue', 'src.queues.clip_queue',
    'src.queues.vision_queue', 'src.queues.embedding_queue',
    'src.queues.translation_queue', 'src.queues.queue_config',
    'src.tasks', 'src.tasks.utils', 'src.tasks.folder_scanners',
    'src.tasks.vision_tasks', 'src.tasks.embedding_tasks',
    'src.tasks.clip_tasks', 'src.tasks.translation_tasks',
    'src.model_services',
    'src.deps',
]:
    sys.modules.setdefault(_mod, MagicMock())

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pathlib import Path

from src.models import Base, Photo as PhotoModel, HistoryAction
from src.db_service import get_last_history_action


@pytest.fixture
def db_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    yield Session


@pytest.fixture
def db(db_factory):
    session = db_factory()
    yield session
    session.close()


# ---------------------------------------------------------------------------
# create_folder tests
# ---------------------------------------------------------------------------

def test_create_folder_inside_allowed_root(tmp_path, db_factory):
    from src.graphs.tools import create_folder
    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory), \
         patch("src.graphs.tools._get_allowed_root", return_value=tmp_path), \
         patch("src.graphs.tools.create_history_action"):
        result = create_folder.invoke({"folder_name": "vacation"})
    assert "vacation" in result
    assert (tmp_path / "vacation").exists()


def test_create_folder_with_parent_path(tmp_path, db_factory):
    from src.graphs.tools import create_folder
    (tmp_path / "events").mkdir()
    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory), \
         patch("src.graphs.tools._get_allowed_root", return_value=tmp_path), \
         patch("src.graphs.tools.create_history_action"):
        result = create_folder.invoke({"folder_name": "2024", "parent_path": "events"})
    assert "2024" in result
    assert (tmp_path / "events" / "2024").exists()


def test_create_folder_escaping_root_returns_error(tmp_path, db_factory):
    from src.graphs.tools import create_folder
    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory), \
         patch("src.graphs.tools._get_allowed_root", return_value=tmp_path):
        result = create_folder.invoke({"folder_name": "escape", "parent_path": "../.."})
    assert "Error" in result


def test_create_folder_already_exists_returns_error(tmp_path, db_factory):
    from src.graphs.tools import create_folder
    (tmp_path / "existing").mkdir()
    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory), \
         patch("src.graphs.tools._get_allowed_root", return_value=tmp_path), \
         patch("src.graphs.tools.create_history_action"):
        result = create_folder.invoke({"folder_name": "existing"})
    assert "Error" in result


def test_create_folder_saves_history_action(tmp_path, db_factory):
    from src.graphs.tools import create_folder
    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory), \
         patch("src.graphs.tools._get_allowed_root", return_value=tmp_path), \
         patch("src.graphs.tools.create_history_action") as mock_hist:
        create_folder.invoke({"folder_name": "archive"})
    mock_hist.assert_called_once()
    call_kwargs = mock_hist.call_args
    assert call_kwargs[1]["action_type"] == "create_folder" or call_kwargs[0][1] == "create_folder"


# ---------------------------------------------------------------------------
# move_photos tests
# ---------------------------------------------------------------------------

def test_move_photos_updates_file_path_in_db(tmp_path, db, db_factory):
    from src.graphs.tools import move_photos
    src_file = tmp_path / "photo.jpg"
    src_file.write_bytes(b"img")
    dest_dir = tmp_path / "dest"

    photo = PhotoModel(hash="h1", file_path=str(src_file))
    db.add(photo)
    db.commit()
    photo_id = photo.id

    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory), \
         patch("src.graphs.tools._get_allowed_root", return_value=tmp_path), \
         patch("src.graphs.tools.create_history_action"):
        result = move_photos.invoke({"photo_ids": [photo_id], "destination_folder": "dest"})

    assert "Moved 1" in result
    check = db_factory().query(PhotoModel).filter(PhotoModel.id == photo_id).first()
    assert check.file_path == str(dest_dir / "photo.jpg")


def test_move_photos_saves_history_action(tmp_path, db, db_factory):
    from src.graphs.tools import move_photos
    src_file = tmp_path / "p.jpg"
    src_file.write_bytes(b"img")

    photo = PhotoModel(hash="h2", file_path=str(src_file))
    db.add(photo)
    db.commit()

    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory), \
         patch("src.graphs.tools._get_allowed_root", return_value=tmp_path), \
         patch("src.graphs.tools.create_history_action") as mock_hist:
        move_photos.invoke({"photo_ids": [photo.id], "destination_folder": "moved"})

    mock_hist.assert_called_once()


def test_move_photos_destination_escapes_root_returns_error(tmp_path, db_factory):
    from src.graphs.tools import move_photos
    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory), \
         patch("src.graphs.tools._get_allowed_root", return_value=tmp_path):
        result = move_photos.invoke({"photo_ids": [1], "destination_folder": "../../etc"})
    assert "Error" in result


def test_move_photos_missing_photo_id_skipped(tmp_path, db_factory):
    from src.graphs.tools import move_photos
    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory), \
         patch("src.graphs.tools._get_allowed_root", return_value=tmp_path), \
         patch("src.graphs.tools.create_history_action"):
        result = move_photos.invoke({"photo_ids": [9999], "destination_folder": "dest"})
    assert "Skipped" in result or "Moved 0" in result


def test_move_photos_creates_destination_if_not_exists(tmp_path, db, db_factory):
    from src.graphs.tools import move_photos
    src_file = tmp_path / "q.jpg"
    src_file.write_bytes(b"img")

    photo = PhotoModel(hash="h3", file_path=str(src_file))
    db.add(photo)
    db.commit()

    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory), \
         patch("src.graphs.tools._get_allowed_root", return_value=tmp_path), \
         patch("src.graphs.tools.create_history_action"):
        move_photos.invoke({"photo_ids": [photo.id], "destination_folder": "brand_new"})

    assert (tmp_path / "brand_new").exists()
