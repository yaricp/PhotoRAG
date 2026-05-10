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


def _make_photo(db) -> Photo:
    p = Photo(hash="abc123", file_path="/tmp/test.jpg")
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
