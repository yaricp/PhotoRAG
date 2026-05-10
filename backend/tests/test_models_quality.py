import sys
from unittest.mock import MagicMock
import sqlalchemy.types

mock_pgvector = MagicMock()
mock_pgvector.sqlalchemy.Vector = lambda size: sqlalchemy.types.JSON()
sys.modules['pgvector'] = mock_pgvector
sys.modules['pgvector.sqlalchemy'] = mock_pgvector.sqlalchemy

import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models import Base, Photo, PhotoQualityIssue
from src.db_service import create_quality_issue, get_quality_summary, get_photos_by_issue_type

TEST_DB = "test_models_quality.sqlite3"
_engine = create_engine(f"sqlite:///{TEST_DB}")
_Session = sessionmaker(bind=_engine)


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    Base.metadata.create_all(bind=_engine)
    yield
    _engine.dispose()
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


@pytest.fixture
def db():
    session = _Session()
    yield session
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()
    session.close()


_photo_counter = 0


def _make_photo(db) -> Photo:
    global _photo_counter
    _photo_counter += 1
    p = Photo(hash=f"abc{_photo_counter:06d}", file_path=f"/tmp/test_{_photo_counter}.jpg")
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def test_create_quality_issue(db):
    photo = _make_photo(db)
    issue = PhotoQualityIssue(photo_id=photo.id, issue_type="blur", score=42.5)
    db.add(issue)
    db.commit()
    db.refresh(issue)
    assert issue.id is not None
    assert issue.issue_type == "blur"
    assert issue.score == 42.5
    assert issue.detected_at is not None


def test_photo_can_have_multiple_issues(db):
    photo = _make_photo(db)
    for itype in ("blur", "no_exif", "thumbnail"):
        db.add(PhotoQualityIssue(photo_id=photo.id, issue_type=itype, score=0.0))
    db.commit()
    assert len(photo.quality_issues) == 3


def test_cascade_delete_removes_issues(db):
    photo = _make_photo(db)
    db.add(PhotoQualityIssue(photo_id=photo.id, issue_type="blur", score=1.0))
    db.commit()
    photo_id = photo.id
    db.delete(photo)
    db.commit()
    remaining = db.query(PhotoQualityIssue).filter_by(photo_id=photo_id).all()
    assert remaining == []


def test_quality_issue_score_is_optional(db):
    photo = _make_photo(db)
    issue = PhotoQualityIssue(photo_id=photo.id, issue_type="no_exif")
    db.add(issue)
    db.commit()
    db.refresh(issue)
    assert issue.score is None


def test_create_quality_issue_service(db):
    photo = _make_photo(db)
    issue = create_quality_issue(db, photo_id=photo.id, issue_type="brightness", score=15.3)
    db.commit()
    assert issue.id is not None
    assert issue.photo_id == photo.id


def test_get_quality_summary_counts(db):
    p1 = _make_photo(db)
    p2 = _make_photo(db)
    create_quality_issue(db, p1.id, "blur", 50.0)
    create_quality_issue(db, p2.id, "blur", 30.0)
    create_quality_issue(db, p1.id, "no_exif", 0.0)
    db.commit()
    summary = get_quality_summary(db)
    assert summary["blur"] == 2
    assert summary["no_exif"] == 1


def test_get_photos_by_issue_type(db):
    p1 = _make_photo(db)
    p2 = _make_photo(db)
    create_quality_issue(db, p1.id, "thumbnail", 900.0)
    create_quality_issue(db, p2.id, "thumbnail", 400.0)
    db.commit()
    photos, total = get_photos_by_issue_type(db, "thumbnail")
    assert total == 2
    ids = {p.id for p in photos}
    assert p1.id in ids and p2.id in ids


def test_get_photos_by_issue_type_pagination(db):
    for _ in range(5):
        p = _make_photo(db)
        create_quality_issue(db, p.id, "entropy", 1.0)
    db.commit()
    photos, total = get_photos_by_issue_type(db, "entropy", skip=0, limit=3)
    assert total == 5
    assert len(photos) == 3
