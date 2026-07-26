# backend/tests/test_tool_archive.py
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
    "src.deps",
]:
    sys.modules.setdefault(_mod, MagicMock())


import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models import Base
from src.models import Photo as PhotoModel


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


def _add_photo(db, tmp_path, filename="photo.jpg", is_archived=False):
    f = tmp_path / filename
    f.write_bytes(b"imgdata")
    photo = PhotoModel(hash=filename, file_path=str(f), is_archived=is_archived)
    db.add(photo)
    db.commit()
    photo_id = photo.id
    db.expunge(photo)
    # re-fetch so the returned object isn't tracked by this session
    return db.query(PhotoModel).filter(PhotoModel.id == photo_id).first()


def test_archive_photos_creates_zip(tmp_path, db, db_factory):
    from src.graphs.tools import archive_photos

    photo = _add_photo(db, tmp_path, "a.jpg")
    zip_path = tmp_path / "MyPhotoArchive.zip"

    with (
        patch("src.graphs.tools.SessionLocal", side_effect=db_factory),
        patch("src.graphs.tools._get_allowed_root", return_value=tmp_path),
        patch("src.graphs.tools.create_history_action"),
    ):
        result = archive_photos.invoke({"photo_ids": [photo.id]})

    assert zip_path.exists()
    assert "Archived 1" in result


def test_archive_photos_appends_to_existing_zip(tmp_path, db, db_factory):
    from src.graphs.tools import archive_photos

    photo1 = _add_photo(db, tmp_path, "first.jpg")
    photo2 = _add_photo(db, tmp_path, "second.jpg")

    zip_path = tmp_path / "MyPhotoArchive.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(str(tmp_path / "first.jpg"), "first.jpg")

    with (
        patch("src.graphs.tools.SessionLocal", side_effect=db_factory),
        patch("src.graphs.tools._get_allowed_root", return_value=tmp_path),
        patch("src.graphs.tools.create_history_action"),
    ):
        archive_photos.invoke({"photo_ids": [photo2.id]})

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    assert "first.jpg" in names
    assert "second.jpg" in names


def test_archive_photos_marks_is_archived_in_db(tmp_path, db, db_factory):
    from src.graphs.tools import archive_photos

    photo = _add_photo(db, tmp_path, "b.jpg", is_archived=False)
    photo_id = photo.id

    with (
        patch("src.graphs.tools.SessionLocal", side_effect=db_factory),
        patch("src.graphs.tools._get_allowed_root", return_value=tmp_path),
        patch("src.graphs.tools.create_history_action"),
    ):
        archive_photos.invoke({"photo_ids": [photo_id]})

    check = db_factory().query(PhotoModel).filter(PhotoModel.id == photo_id).first()
    assert check.is_archived is True


def test_archive_photos_skips_already_archived_status(tmp_path, db, db_factory):
    from src.graphs.tools import archive_photos

    photo = _add_photo(db, tmp_path, "c.jpg", is_archived=True)

    with (
        patch("src.graphs.tools.SessionLocal", side_effect=db_factory),
        patch("src.graphs.tools._get_allowed_root", return_value=tmp_path),
        patch("src.graphs.tools.create_history_action") as mock_hist,
    ):
        archive_photos.invoke({"photo_ids": [photo.id]})

    call_kwargs = mock_hist.call_args
    undo_data = call_kwargs[1]["undo_data"] if call_kwargs[1] else call_kwargs[0][4]
    assert undo_data["newly_archived_ids"] == []


def test_archive_photos_saves_history_with_newly_archived_ids(tmp_path, db, db_factory):
    from src.graphs.tools import archive_photos

    photo = _add_photo(db, tmp_path, "d.jpg", is_archived=False)
    photo_id = photo.id

    with (
        patch("src.graphs.tools.SessionLocal", side_effect=db_factory),
        patch("src.graphs.tools._get_allowed_root", return_value=tmp_path),
        patch("src.graphs.tools.create_history_action") as mock_hist,
    ):
        archive_photos.invoke({"photo_ids": [photo_id]})

    mock_hist.assert_called_once()
    call_kwargs = mock_hist.call_args
    undo_data = call_kwargs[1]["undo_data"] if call_kwargs[1] else call_kwargs[0][4]
    assert photo_id in undo_data["newly_archived_ids"]


def test_archive_photos_skips_missing_files(tmp_path, db, db_factory):
    from src.graphs.tools import archive_photos

    photo = PhotoModel(hash="missing", file_path=str(tmp_path / "nope.jpg"), is_archived=False)
    db.add(photo)
    db.commit()
    photo_id = photo.id

    with (
        patch("src.graphs.tools.SessionLocal", side_effect=db_factory),
        patch("src.graphs.tools._get_allowed_root", return_value=tmp_path),
        patch("src.graphs.tools.create_history_action"),
    ):
        result = archive_photos.invoke({"photo_ids": [photo_id]})

    assert "Skipped" in result or "Archived 0" in result
