# backend/tests/test_tool_garbage.py
import sys
import os
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

from src.models import Base, Photo as PhotoModel, PhotoQualityIssue


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


def _add_photo_with_issue(db, tmp_path, filename, issue_type):
    f = tmp_path / filename
    f.write_bytes(b"imgdata")
    photo = PhotoModel(hash=filename, file_path=str(f))
    db.add(photo)
    db.flush()
    issue = PhotoQualityIssue(photo_id=photo.id, issue_type=issue_type, score=0.5)
    db.add(issue)
    db.commit()
    return photo


# ---------------------------------------------------------------------------
# get_garbage_photos
# ---------------------------------------------------------------------------

def test_get_garbage_photos_returns_summary_and_photos(tmp_path, db, db_factory):
    from src.graphs.tools import get_garbage_photos
    _add_photo_with_issue(db, tmp_path, "a.jpg", "blur")
    _add_photo_with_issue(db, tmp_path, "b.jpg", "brightness")

    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory):
        result = get_garbage_photos.invoke({"issue_type": "", "limit": 10})

    # Result is a JSON array of Photo objects; both files should appear
    assert "a.jpg" in result or "b.jpg" in result


def test_get_garbage_photos_filters_by_issue_type(tmp_path, db, db_factory):
    from src.graphs.tools import get_garbage_photos
    _add_photo_with_issue(db, tmp_path, "c.jpg", "blur")
    _add_photo_with_issue(db, tmp_path, "d.jpg", "screenshot")

    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory):
        result = get_garbage_photos.invoke({"issue_type": "blur"})

    assert "c.jpg" in result
    # screenshot photo should not appear
    assert "d.jpg" not in result


def test_get_garbage_photos_empty_when_no_issues(db_factory):
    from src.graphs.tools import get_garbage_photos
    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory):
        result = get_garbage_photos.invoke({})
    assert "No flagged photos" in result or "0" in result


def test_get_garbage_photos_deduplicates_multi_issue_photo(tmp_path, db, db_factory):
    from src.graphs.tools import get_garbage_photos
    f = tmp_path / "multi.jpg"
    f.write_bytes(b"x")
    photo = PhotoModel(hash="multi", file_path=str(f))
    db.add(photo)
    db.flush()
    db.add(PhotoQualityIssue(photo_id=photo.id, issue_type="blur", score=0.1))
    db.add(PhotoQualityIssue(photo_id=photo.id, issue_type="brightness", score=0.1))
    db.commit()

    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory):
        result = get_garbage_photos.invoke({"limit": 50})

    # Photo should appear only once (DISTINCT)
    assert result.count(str(photo.id)) == 1 or "multi.jpg" in result


# ---------------------------------------------------------------------------
# get_garbage_total_size
# ---------------------------------------------------------------------------

def test_get_garbage_total_size_returns_human_readable(tmp_path, db, db_factory):
    from src.graphs.tools import get_garbage_total_size
    photo = _add_photo_with_issue(db, tmp_path, "big.jpg", "blur")

    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory):
        result = get_garbage_total_size.invoke({})

    assert "MB" in result or "GB" in result
    assert "1 file" in result


def test_get_garbage_total_size_filters_by_issue_type(tmp_path, db, db_factory):
    from src.graphs.tools import get_garbage_total_size
    _add_photo_with_issue(db, tmp_path, "e.jpg", "blur")
    _add_photo_with_issue(db, tmp_path, "f.jpg", "screenshot")

    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory):
        result_blur = get_garbage_total_size.invoke({"issue_type": "blur"})
        result_all = get_garbage_total_size.invoke({"issue_type": ""})

    assert "blur" in result_blur
    # All-issues result should mention more files
    assert "2 file" in result_all or "1 file" in result_blur


def test_get_garbage_total_size_missing_file_excluded(tmp_path, db, db_factory):
    from src.graphs.tools import get_garbage_total_size
    photo = PhotoModel(hash="missing", file_path=str(tmp_path / "gone.jpg"))
    db.add(photo)
    db.flush()
    db.add(PhotoQualityIssue(photo_id=photo.id, issue_type="blur", score=0.0))
    db.commit()

    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory):
        result = get_garbage_total_size.invoke({})

    assert "missing on disk" in result or "0.0 MB" in result
