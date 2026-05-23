import sys
from unittest.mock import MagicMock, patch

# src.observer → src.incoming_pipeline → src.tasks.quality_tasks (not installed).
# Mock before src.observer is imported so the import chain resolves cleanly.
sys.modules.setdefault('src.incoming_pipeline', MagicMock())

from src.observer import PhotoEventHandler

@patch('src.observer.os.stat')
@patch('src.observer.SessionLocal')
@patch('src.observer.check_photo_hash_exists')
@patch('src.observer.create_photo_record')
@patch('src.observer.start_pipeline')
@patch('src.observer.generate_file_hash')
def test_on_created_triggers_4_parallel_tasks(mock_hash, mock_pipeline, mock_create, mock_check, mock_db, mock_stat):
    mock_hash.return_value = "fake_hash"
    mock_check.return_value = None # Assume photo doesn't exist
    mock_photo = MagicMock()
    mock_photo.id = 123
    mock_create.return_value = mock_photo
    
    # Mock os.stat return value
    mock_stat_res = MagicMock()
    mock_stat_res.st_birthtime = 1600000000.0
    mock_stat.return_value = mock_stat_res
    
    handler = PhotoEventHandler(destination_root_folder="/dest")
    mock_event = MagicMock()
    mock_event.is_directory = False
    mock_event.src_path = "test_photo.jpg"
    
    handler.on_created(mock_event)
    
    # Verify sync registration
    mock_hash.assert_called_once_with("test_photo.jpg")
    mock_create.assert_called_once()
    
    # Verify tasks are dispatched with the ID
    mock_pipeline.assert_called_once_with(123)

@patch('src.observer.start_pipeline')
def test_on_created_ignores_non_photos(mock_pipeline):
    handler = PhotoEventHandler(destination_root_folder="/dest")
    mock_event = MagicMock()
    mock_event.is_directory = False
    mock_event.src_path = "test_data.txt"
    
    handler.on_created(mock_event)
    
    mock_pipeline.assert_not_called()
