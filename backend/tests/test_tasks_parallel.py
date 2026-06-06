import sys
from datetime import datetime
from unittest.mock import MagicMock, patch

import sqlalchemy.types

# ATOMIC MOCK: Must happen before any project imports
mock_pgvector = MagicMock()
mock_pgvector.sqlalchemy.Vector = lambda size: sqlalchemy.types.JSON()
sys.modules["pgvector"] = mock_pgvector
sys.modules["pgvector.sqlalchemy"] = mock_pgvector.sqlalchemy

import os

import pytest
import sqlalchemy.orm
from sqlalchemy import create_engine

from src.db_service import create_photo_record
from src.models import Base, Photo
from src.tasks.clip_tasks import metadata_task

TEST_DB_FILE = "test_accuracy.sqlite3"
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


@pytest.fixture(autouse=True)
def patch_session():
    with patch("src.tasks.clip_tasks.SessionLocal", TestSessionLocal):
        with patch("src.database.SessionLocal", TestSessionLocal):
            yield


@pytest.fixture
def db_session():
    session = TestSessionLocal()
    yield session
    session.query(Photo).delete()
    session.commit()
    session.close()


def test_atomic_creation_with_file_timestamp(db_session):
    file_now = datetime(2020, 1, 1)
    photo = create_photo_record(db_session, "hash_1", "test.jpg", file_created_at=file_now)

    assert photo.file_created_at == file_now
    assert photo.captured_at is None  # Should be empty until metadata task runs


@patch("src.tasks.clip_tasks.parse_datetime")
@patch("src.tasks.clip_tasks.extract_exif")
def test_metadata_task_populates_captured_at(mock_extract, mock_parse, db_session):
    file_now = datetime(2020, 1, 1)
    captured_now = datetime(2019, 12, 25, 10, 30)  # True camera time

    # 1. Start with file system time
    photo = create_photo_record(db_session, "hash_2", "test.jpg", file_created_at=file_now)

    # 2. Mock EXIF returning camera time
    mock_extract.return_value = {"Model": "Sony A7"}
    mock_parse.return_value = captured_now

    db_session.commit()

    # 3. Run Metadata task
    metadata_task.call_local(photo.id, phase="test_phase")

    db_session.expire_all()
    photo = db_session.query(Photo).get(photo.id)
    assert photo.file_created_at == file_now  # Preserved
    assert photo.captured_at == captured_now  # Updated from EXIF
