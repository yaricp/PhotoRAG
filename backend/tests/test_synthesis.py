import pytest
from unittest.mock import MagicMock, patch
import os
import sys
import numpy as np

# ATOMIC MOCK
mock_pgvector = MagicMock()
mock_pgvector.sqlalchemy.Vector = lambda size: MagicMock()
sys.modules['pgvector'] = mock_pgvector
sys.modules['pgvector.sqlalchemy'] = mock_pgvector.sqlalchemy
sys.modules['sentence_transformers'] = MagicMock()

from src.tasks import check_and_trigger_finalization, final_embedding_task
from src.models import Photo, PhotoTag, PhotoCategory, Tag, Category, Geoposition

@pytest.fixture
def mock_db():
    db = MagicMock()
    return db

def test_finalizer_barrier_triggers_when_ready(mock_db):
    photo = Photo(id=1, captured_at="2024-01-01", description="A fine day")
    mock_db.query.return_value.filter.return_value.first.return_value = photo
    mock_db.query.return_value.filter_by.return_value.count.side_effect = [1, 1] 
    
    with patch('src.tasks.final_embedding_task') as mock_final:
        check_and_trigger_finalization(mock_db, 1)
        mock_final.assert_called_once_with(1)

def test_finalizer_barrier_waits_when_missing_vision(mock_db):
    photo = Photo(id=1, captured_at="2024-01-01", description=None)
    mock_db.query.return_value.filter.return_value.first.return_value = photo
    mock_db.query.return_value.filter_by.return_value.count.return_value = 1
    
    with patch('src.tasks.final_embedding_task') as mock_final:
        check_and_trigger_finalization(mock_db, 1)
        mock_final.assert_not_called()

# Updated: Patch the registry instead of sentence_transformers
@patch('src.tasks.registry') 
@patch('src.tasks.SessionLocal')
def test_final_embedding_generation_logic(mock_session, mock_registry):
    db = mock_session.return_value
    photo = Photo(id=1, description="Magnificent Forest")
    photo.tags_rel = [MagicMock(tag=Tag(name="Tree"))]
    photo.categories_rel = [MagicMock(category=Category(name="Nature"))]
    
    db.query.return_value.filter.return_value.first.return_value = photo
    db.query.return_value.filter_by.return_value.first.return_value = Geoposition(address="Berlin")
    
    # Registry mock setup
    mock_model = MagicMock()
    mock_model.encode.return_value = np.array([0.1] * 768)
    mock_registry.nomic_embedder = mock_model
    
    final_embedding_task.call_local(1)
    
    assert photo.embedding == ([0.1] * 768)
    db.commit.assert_called()
