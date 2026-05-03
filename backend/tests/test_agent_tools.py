import pytest
from unittest.mock import MagicMock, patch
from src.graphs.tools import search_photos_semantic, search_photos_metadata, get_photo_details

@pytest.fixture
def mock_db():
    with patch("src.graphs.tools.SessionLocal") as mock:
        yield mock

def test_search_photos_semantic_success(mock_db):
    mock_session = mock_db.return_value
    
    mock_photo = MagicMock()
    mock_photo.id = 1
    mock_photo.file_path = "test.jpg"
    mock_photo.description = "A cat"
    
    with patch("src.graphs.tools.get_photos_by_vector", return_value=[mock_photo]):
        result = search_photos_semantic.invoke({"query": "cat", "k": 1})
        assert "ID: 1" in result
        assert "Description: A cat" in result

def test_search_photos_semantic_empty(mock_db):
    mock_session = mock_db.return_value
    with patch("src.graphs.tools.get_photos_by_vector", return_value=[]):
        result = search_photos_semantic.invoke({"query": "dog"})
        assert "No photos found" in result

def test_search_photos_metadata_success(mock_db):
    mock_session = mock_db.return_value
    
    mock_photo = MagicMock()
    mock_photo.id = 2
    mock_photo.file_path = "nature.jpg"
    mock_photo.description = "Forest"
    
    with patch("src.graphs.tools.get_all_photos", return_value=([mock_photo], 1)):
        result = search_photos_metadata.invoke({"category_id": 1})
        assert "Found 1 photos" in result
        assert "ID: 2" in result

def test_get_photo_details_success(mock_db):
    mock_session = mock_db.return_value
    
    mock_photo = MagicMock()
    mock_photo.id = 3
    mock_photo.file_path = "office.jpg"
    mock_photo.captured_at = "2023-01-01"
    mock_photo.description = "Work"
    mock_photo.ocr_text = "Hello"
    mock_photo.is_doc = True
    mock_photo.camera = MagicMock(make="Canon", model="EOS")
    mock_photo.tags_rel = []
    mock_photo.categories_rel = []
    
    with patch("src.graphs.tools.get_photo_by_id", return_value=mock_photo):
        result = get_photo_details.invoke({"photo_id": 3})
        assert "ID: 3" in result
        assert "Camera Make: Canon" in result
        assert "Is Document: True" in result
