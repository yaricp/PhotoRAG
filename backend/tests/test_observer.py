import time
import os
from unittest.mock import MagicMock, patch
from src.observer import PhotoEventHandler

def test_on_created_triggers_task():
    # Mock the task and the hash function
    mock_task = MagicMock()
    mock_hash = MagicMock(return_value="fake_hash")
    
    with patch('src.observer.process_photo_task', mock_task), \
         patch('src.observer.generate_file_hash', mock_hash):
        
        handler = PhotoEventHandler()
        mock_event = MagicMock()
        mock_event.is_directory = False
        mock_event.src_path = "test_photo.jpg"
        
        handler.on_created(mock_event)
        
        mock_hash.assert_called_once_with("test_photo.jpg")
        mock_task.assert_called_once_with("test_photo.jpg")

def test_on_created_ignores_non_photos():
    mock_task = MagicMock()
    with patch('src.observer.process_photo_task', mock_task):
        handler = PhotoEventHandler()
        mock_event = MagicMock()
        mock_event.is_directory = False
        mock_event.src_path = "test_data.txt"
        
        handler.on_created(mock_event)
        
        mock_task.assert_not_called()
