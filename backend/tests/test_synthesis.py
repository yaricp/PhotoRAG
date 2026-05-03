import pytest
from unittest.mock import MagicMock, patch
import os
import sys

# ATOMIC MOCK
sys.modules['sentence_transformers'] = MagicMock()

from src.tasks.embedding_tasks import final_embedding_task
from src.models import Photo, PhotoTag, PhotoCategory, Tag, Category, Geoposition

@pytest.fixture
def mock_db():
    db = MagicMock()
    return db

@patch('src.tasks.embedding_tasks.registry') 
@patch('src.tasks.embedding_tasks.SessionLocal')
@patch('src.tasks.embedding_tasks.store_photo_embedding')
@patch('src.tasks.utils._finish_task')
def test_final_embedding_generation_logic(mock_finish_task, mock_store, mock_session, mock_registry):
    db = mock_session.return_value
    photo = Photo(id=1, description="Magnificent Forest")
    photo.tags_rel = [MagicMock(tag=Tag(name="Tree"))]
    photo.categories_rel = [MagicMock(category=Category(name="Nature"))]
    
    db.query.return_value.filter.return_value.first.return_value = photo
    db.query.return_value.filter_by.return_value.first.return_value = Geoposition(address="Berlin")
    
    # Registry mock setup
    mock_model = MagicMock()
    mock_model.name = "test_model"
    mock_registry.nomic_embedder = mock_model
    mock_registry.embedder_encode_text.return_value = [0.1] * 768
    
    final_embedding_task.call_local(1, phase="test_phase")
    
    mock_store.assert_called_once_with(db, 1, [0.1]*768, "test_model")
    mock_finish_task.assert_called_once_with(photo_id=1, phase="test_phase", name="final_embedding_task")
    db.commit.assert_called()
