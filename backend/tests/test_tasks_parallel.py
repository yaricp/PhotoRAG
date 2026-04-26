import sys
from unittest.mock import MagicMock, patch
import sqlalchemy.types

# ATOMIC MOCK: Must happen before any project imports
mock_pgvector = MagicMock()
mock_pgvector.sqlalchemy.Vector = lambda size: sqlalchemy.types.JSON()
sys.modules['pgvector'] = mock_pgvector
sys.modules['pgvector.sqlalchemy'] = mock_pgvector.sqlalchemy

import pytest
import sqlalchemy.orm
import os
from sqlalchemy import create_engine
from src.models import Photo, Base
from src.tasks import metadata_task, clip_task, vision_task, ocr_task
from src.db_service import create_photo_record

TEST_DB_FILE = "test_id_based.sqlite3"
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
    with patch('src.tasks.SessionLocal', TestSessionLocal):
        with patch('src.database.SessionLocal', TestSessionLocal):
            yield

@pytest.fixture
def db_session():
    session = TestSessionLocal()
    yield session
    session.query(Photo).delete()
    session.commit()
    session.close()

@patch('src.tasks.get_exif_data', return_value={"model": "Test Camera"})
def test_metadata_task_by_id(mock_exif, db_session):
    # Step 1: Sync Creation (Simulating Observer)
    photo = create_photo_record(db_session, "id_hash_1", "test.jpg")
    photo_id = photo.id
    
    # Step 2: Async Launch (by ID)
    metadata_task.call_local(photo_id)
    
    db_session.refresh(photo)
    assert photo.exif_data["model"] == "Test Camera"

@patch('src.tasks.ClipTagger')
def test_clip_task_by_id(mock_tagger_class, db_session):
    photo = create_photo_record(db_session, "id_hash_2", "test.jpg")
    mock_tagger = mock_tagger_class.return_value
    mock_tagger.generate_keywords.return_value = ["tag1"]
    
    clip_task.call_local(photo.id)
    
    db_session.refresh(photo)
    assert "tag1" in photo.keywords
