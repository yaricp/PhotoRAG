import pytest
from unittest.mock import MagicMock, patch, PropertyMock
import sys

# ATOMIC MOCKS
sys.modules['pgvector'] = MagicMock()
sys.modules['pgvector.sqlalchemy'] = MagicMock()
sys.modules['sentence_transformers'] = MagicMock()

from src.tasks import download_models_task
from src.models import ModelState
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models import Base

TEST_DB_URL = "sqlite:///:memory:"
test_engine = create_engine(TEST_DB_URL)
TestSessionLocal = sessionmaker(bind=test_engine)

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)

@pytest.fixture
def db_session():
    session = TestSessionLocal()
    yield session
    session.query(ModelState).delete()
    session.commit()
    session.close()


# Patch at the source module since ClipTagger/QwenVisionGenerator are lazy imports
@patch('src.ai.vision.QwenVisionGenerator')
@patch('src.ai.clip.ClipTagger')
@patch('src.tasks.SessionLocal')
def test_download_task_skips_if_ready(mock_session_class, mock_clip_class, mock_vision_class, db_session):
    """If all models are already 'ready', no download() should be triggered."""
    mock_session_class.return_value = db_session

    # Pre-seed all statuses as ready
    for name in ["clip", "vision", "embedding"]:
        db_session.merge(ModelState(name=name, status="ready"))
    db_session.commit()

    download_models_task.call_local()

    # download() must NOT have been called on any model
    mock_clip_class.return_value.download.assert_not_called()
    mock_vision_class.return_value.download.assert_not_called()


@patch('src.ai.vision.QwenVisionGenerator')
@patch('src.ai.clip.ClipTagger')
@patch('src.tasks.SessionLocal')
def test_download_task_runs_if_pending(mock_session_class, mock_clip_class, mock_vision_class, db_session):
    """If models are not 'ready', download() must be called directly (not via registry)."""
    mock_session_class.return_value = db_session
    # No ModelState rows — status will be None → not "ready"

    download_models_task.call_local()

    # download() MUST have been called on each model directly
    mock_clip_class.return_value.download.assert_called_once()
    mock_vision_class.return_value.download.assert_called_once()

    # Final statuses must be "ready"
    states = {s.name: s.status for s in db_session.query(ModelState).all()}
    assert states["clip"] == "ready"
    assert states["vision"] == "ready"
    assert states["embedding"] == "ready"
