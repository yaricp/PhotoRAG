import sys
from unittest.mock import MagicMock
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

TEST_DB_FILE = "test_atomic.sqlite3"
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
        yield

@pytest.fixture
def db_session():
    session = TestSessionLocal()
    yield session
    # Clear after every test to ensure isolation
    session.query(Photo).delete()
    session.commit()
    session.close()

from unittest.mock import patch

@patch('src.tasks.get_exif_data', return_value={"model": "Test Camera"})
@patch('src.db_service.generate_file_hash', return_value="parallel_hash_1")
def test_metadata_task_updates_db(mock_hash, mock_exif, db_session):
    metadata_task.call_local("test.jpg")
    photo = db_session.query(Photo).filter_by(hash="parallel_hash_1").first()
    assert photo is not None
    assert photo.exif_data["model"] == "Test Camera"

@patch('src.tasks.ClipTagger')
@patch('src.db_service.generate_file_hash', return_value="parallel_hash_2")
def test_clip_task_updates_db(mock_hash, mock_tagger_class, db_session):
    mock_tagger = mock_tagger_class.return_value
    mock_tagger.generate_keywords.return_value = ["tag1", "tag2"]
    
    clip_task.call_local("test.jpg")
    photo = db_session.query(Photo).filter_by(hash="parallel_hash_2").first()
    assert photo is not None
    assert "tag1" in photo.keywords

@patch('src.tasks.QwenVisionGenerator')
@patch('src.db_service.generate_file_hash', return_value="parallel_hash_3")
def test_vision_task_updates_db(mock_hash, mock_gen_class, db_session):
    mock_gen = mock_gen_class.return_value
    mock_gen.describe_scene.return_value = "A beautiful scene"
    
    vision_task.call_local("test.jpg")
    photo = db_session.query(Photo).filter_by(hash="parallel_hash_3").first()
    assert photo is not None
    assert photo.description == "A beautiful scene"

@patch('src.tasks.extract_text_from_image', return_value="Detected Text")
@patch('src.db_service.generate_file_hash', return_value="parallel_hash_4")
def test_ocr_task_updates_db(mock_hash, mock_ocr, db_session):
    ocr_task.call_local("test.jpg")
    photo = db_session.query(Photo).filter_by(hash="parallel_hash_4").first()
    assert photo is not None
    assert photo.ocr_text == "Detected Text"
