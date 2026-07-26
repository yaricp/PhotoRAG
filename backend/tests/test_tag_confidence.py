# ATOMIC MOCK
import os
import sys
from unittest.mock import MagicMock

import pytest
import sqlalchemy.orm
import sqlalchemy.types
from sqlalchemy import create_engine

from src.db_service import add_photo_tag_with_score
from src.models import Base, Photo, PhotoTag, Tag

TEST_DB_FILE = "test_confidence.sqlite3"
test_engine = create_engine(f"sqlite:///{TEST_DB_FILE}")


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    if os.path.exists(TEST_DB_FILE):
        os.remove(TEST_DB_FILE)
    Base.metadata.create_all(bind=test_engine)
    yield
    if os.path.exists(TEST_DB_FILE):
        os.remove(TEST_DB_FILE)


TestSessionLocal = sqlalchemy.orm.sessionmaker(bind=test_engine)


@pytest.fixture
def db_session():
    session = TestSessionLocal()
    yield session
    session.query(PhotoTag).delete()
    session.query(Photo).delete()
    session.query(Tag).delete()
    session.commit()
    session.close()


def test_add_tag_with_confidence(db_session):
    photo = Photo(hash="tag_hash", file_path="tag.jpg")
    db_session.add(photo)
    db_session.commit()

    # Use service to add tag with score
    add_photo_tag_with_score(db_session, photo.id, "Forest", 0.92)

    # Verify persistence
    pt = db_session.query(PhotoTag).filter_by(photo_id=photo.id).first()
    assert pt.tag.name == "Forest"
    assert pt.confidence_score == 0.92


def test_tag_threshold_logic(db_session):
    # This is a unit test for the logic we'll use in the task
    scores = [("Nature", 0.8), ("Ghost", 0.1), ("Mountain", 0.51)]
    confident = [t for t, s in scores if s > 0.5]

    assert "Nature" in confident
    assert "Mountain" in confident
    assert "Ghost" not in confident
