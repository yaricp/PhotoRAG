import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from src.tasks import download_models_task
from src.models import Base, ModelState
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

# SETUP LOCAL TEST DB
TEST_DB_URL = "sqlite:///:memory:"
test_engine = create_engine(TEST_DB_URL)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

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

@patch('src.tasks.registry')
@patch('src.tasks.SessionLocal')
def test_download_models_task_lifecycle(mock_session_class, mock_registry, db_session):
    mock_session_class.return_value = db_session
    
    # Use call_local for synchronous execution in tests
    download_models_task.call_local()
    
    # Verify model states
    states = {s.name: s.status for s in db_session.query(ModelState).all()}
    assert "clip" in states
    assert states["clip"] == "ready"
    assert states["vision"] == "ready"
    assert states["embedding"] == "ready"

@patch('src.tasks.registry')
@patch('src.tasks.SessionLocal')
def test_bootstrap_sets_error_status(mock_session_class, mock_registry, db_session):
    mock_session_class.return_value = db_session
    
    # Simulate clip failure
    # Need to simulate failure on property access
    type(mock_registry).clip_tagger = PropertyMock(side_effect=Exception("Fail"))
    
    download_models_task.call_local()
    
    state = db_session.query(ModelState).filter_by(name="clip").first()
    assert state is not None
    assert state.status == "error"
