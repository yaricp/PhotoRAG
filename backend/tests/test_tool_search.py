# backend/tests/test_tool_search.py
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
    "src.deps",
]:
    sys.modules.setdefault(_mod, MagicMock())

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models import Base, Camera, PhotoTag, Tag
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


def _add_photo(db, tmp_path, filename="p.jpg", **kwargs):
    f = tmp_path / filename
    f.write_bytes(b"img")
    photo = PhotoModel(hash=filename, file_path=str(f), **kwargs)
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return photo


# ---------------------------------------------------------------------------
# get_photos_by_tag_id
# ---------------------------------------------------------------------------


def test_get_photos_by_tag_id_returns_matching_photos(tmp_path, db, db_factory):
    from src.graphs.tools import get_photos_by_tag_id

    photo = _add_photo(db, tmp_path, "tagged.jpg")
    tag = Tag(name="sunset")
    db.add(tag)
    db.flush()
    db.add(PhotoTag(photo_id=photo.id, tag_id=tag.id, confidence_score=1.0))
    db.commit()

    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory):
        result = get_photos_by_tag_id.invoke({"tag_id": tag.id})

    assert "tagged.jpg" in result


def test_get_photos_by_tag_id_returns_empty_message_when_none(db_factory):
    from src.graphs.tools import get_photos_by_tag_id

    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory):
        result = get_photos_by_tag_id.invoke({"tag_id": 9999})
    assert "No photos" in result


def test_get_photos_by_tag_id_does_not_return_untagged_photo(tmp_path, db, db_factory):
    from src.graphs.tools import get_photos_by_tag_id

    _add_photo(db, tmp_path, "untagged.jpg")
    tag = Tag(name="ocean")
    db.add(tag)
    db.commit()

    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory):
        result = get_photos_by_tag_id.invoke({"tag_id": tag.id})

    assert "untagged.jpg" not in result


# ---------------------------------------------------------------------------
# search_photos_by_exif
# ---------------------------------------------------------------------------


def test_search_photos_by_exif_width_filter(tmp_path, db, db_factory):
    from src.graphs.tools import search_photos_by_exif

    wide = _add_photo(db, tmp_path, "wide.jpg", image_width=5000, image_height=3000)
    narrow = _add_photo(db, tmp_path, "narrow.jpg", image_width=800, image_height=600)

    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory):
        result = search_photos_by_exif.invoke({"width_min": 4000})

    assert "wide.jpg" in result
    assert "narrow.jpg" not in result


def test_search_photos_by_exif_iso_filter(tmp_path, db, db_factory):
    from src.graphs.tools import search_photos_by_exif

    high_iso = _add_photo(db, tmp_path, "high_iso.jpg", iso=6400)
    low_iso = _add_photo(db, tmp_path, "low_iso.jpg", iso=100)

    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory):
        result = search_photos_by_exif.invoke({"iso_min": 3200})

    assert "high_iso.jpg" in result
    assert "low_iso.jpg" not in result


def test_search_photos_by_exif_no_match(db_factory):
    from src.graphs.tools import search_photos_by_exif

    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory):
        result = search_photos_by_exif.invoke({"width_min": 99999})
    assert "No photos" in result


def test_search_photos_by_exif_camera_make(tmp_path, db, db_factory):
    from src.graphs.tools import search_photos_by_exif

    cam = Camera(make="Canon", model="EOS 5D")
    db.add(cam)
    db.flush()
    canon_photo = _add_photo(db, tmp_path, "canon.jpg", camera_id=cam.id)
    other_photo = _add_photo(db, tmp_path, "other.jpg")

    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory):
        result = search_photos_by_exif.invoke({"camera_make": "canon"})

    assert "canon.jpg" in result
    assert "other.jpg" not in result


# ---------------------------------------------------------------------------
# filter_photos
# ---------------------------------------------------------------------------


def test_filter_photos_returns_all_without_filters(tmp_path, db, db_factory):
    from src.graphs.tools import filter_photos

    _add_photo(db, tmp_path, "f1.jpg")
    _add_photo(db, tmp_path, "f2.jpg")

    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory):
        result = filter_photos.invoke({"limit": 50})

    assert "f1.jpg" in result
    assert "f2.jpg" in result


def test_filter_photos_is_doc_filter(tmp_path, db, db_factory):
    from src.graphs.tools import filter_photos

    _add_photo(db, tmp_path, "doc.jpg", is_doc=True)
    _add_photo(db, tmp_path, "photo.jpg", is_doc=False)

    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory):
        result = filter_photos.invoke({"is_doc": True})

    assert "doc.jpg" in result
    assert "photo.jpg" not in result


def test_filter_photos_returns_no_photos_message(db_factory):
    from src.graphs.tools import filter_photos

    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory):
        result = filter_photos.invoke({"is_doc": True})
    assert "No photos" in result
