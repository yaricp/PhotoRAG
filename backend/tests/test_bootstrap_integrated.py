import pytest
import sys
from unittest.mock import MagicMock, patch
import sqlalchemy.types
import sqlalchemy.orm
import os
import uuid
from sqlalchemy import create_engine
from src.models import Base, ModelState
from src.tasks import download_models_task

# ATOMIC MOCK: Must happen before any project imports
mock_pgvector = MagicMock()
mock_pgvector.sqlalchemy.Vector = lambda size: sqlalchemy.types.JSON()
sys.modules['pgvector'] = mock_pgvector
sys.modules['pgvector.sqlalchemy'] = mock_pgvector.sqlalchemy

@pytest.fixture
def isolated_db():
    db_name = f"test_iso_{uuid.uuid4().hex}.sqlite3"
    engine = create_engine(f"sqlite:///{db_name}")
    Base.metadata.create_all(bind=engine)
    
    SessionLocal = sqlalchemy.orm.sessionmaker(bind=engine)
    session = SessionLocal()
    
    # Pre-seed
    session.add(ModelState(name="clip", status="pending"))
    session.add(ModelState(name="vision", status="pending"))
    session.add(ModelState(name="embedding", status="pending"))
    session.commit()
    
    with patch('src.tasks.SessionLocal', return_value=session):
        yield session
    
    session.close()
    if os.path.exists(db_name):
        os.remove(db_name)

# CRITICAL: Patch BOTH AI modules globally for all tests in this file
@patch('src.tasks.ClipTagger')
@patch('src.tasks.QwenVisionGenerator')
def test_download_models_task_lifecycle(mock_vision_class, mock_clip_class, isolated_db):
    download_models_task.call_local()
    
    states = isolated_db.query(ModelState).all()
    assert len(states) == 3
    for s in states:
        assert s.status == "ready"

@patch('src.tasks.ClipTagger')
@patch('src.tasks.QwenVisionGenerator')
def test_bootstrap_sets_error_status(mock_vision_class, mock_clip_class, isolated_db):
    # Simulate a crash in CLIP
    mock_clip_class.return_value.download.side_effect = Exception("Down")
    
    download_models_task.call_local()
    
    # CLIP should be error
    clip_state = isolated_db.query(ModelState).filter_by(name="clip").first()
    assert clip_state.status == "error"
    
    # Vision should proceed to ready (because it was mocked)
    vision_state = isolated_db.query(ModelState).filter_by(name="vision").first()
    assert vision_state.status == "ready"
