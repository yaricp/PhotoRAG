import sys
from unittest.mock import MagicMock, mock_open, patch

# src.observer → src.incoming_pipeline → src.tasks.quality_tasks (not installed).
# Mock before src.observer is imported so the import chain resolves cleanly.
sys.modules.setdefault("src.incoming_pipeline", MagicMock())

from src.observer import PhotoEventHandler, wait_until_file_ready


@patch("src.observer.SessionLocal")
@patch("src.observer.check_photo_hash_exists")
@patch("src.observer.create_photo_record")
@patch("src.observer.start_pipeline")
@patch("src.observer.generate_file_hash")
@patch("src.observer.wait_until_file_ready")
def test_on_created_triggers_4_parallel_tasks(mock_ready, mock_hash, mock_pipeline, mock_create, mock_check, mock_db):
    mock_ready.return_value = True
    mock_hash.return_value = "fake_hash"
    mock_check.return_value = None  # Assume photo doesn't exist
    mock_photo = MagicMock()
    mock_photo.id = 123
    mock_create.return_value = mock_photo

    handler = PhotoEventHandler(destination_root_folder="/dest")
    mock_event = MagicMock()
    mock_event.is_directory = False
    mock_event.src_path = "test_photo.jpg"

    handler.on_created(mock_event)

    mock_ready.assert_called_once_with("test_photo.jpg")
    # Verify sync registration
    mock_hash.assert_called_once_with("test_photo.jpg")
    mock_create.assert_called_once()

    # Verify tasks are dispatched with the ID
    mock_pipeline.assert_called_once_with(123)


@patch("src.observer.start_pipeline")
@patch("src.observer.wait_until_file_ready")
def test_on_created_ignores_non_photos(mock_ready, mock_pipeline):
    handler = PhotoEventHandler(destination_root_folder="/dest")
    mock_event = MagicMock()
    mock_event.is_directory = False
    mock_event.src_path = "test_data.txt"

    handler.on_created(mock_event)

    mock_ready.assert_not_called()
    mock_pipeline.assert_not_called()


@patch("src.observer.generate_file_hash")
@patch("src.observer.wait_until_file_ready")
def test_on_created_waits_for_file_ready_before_hashing(mock_ready, mock_hash):
    mock_ready.return_value = False
    handler = PhotoEventHandler(destination_root_folder="/dest")
    mock_event = MagicMock()
    mock_event.is_directory = False
    mock_event.src_path = "locked_photo.jpg"

    handler.on_created(mock_event)

    mock_ready.assert_called_once_with("locked_photo.jpg")
    mock_hash.assert_not_called()


@patch("src.observer.time.sleep")
@patch("builtins.open", new_callable=mock_open, read_data=b"x")
@patch("src.observer.os.path.getsize")
def test_wait_until_file_ready_returns_true_after_size_is_stable(mock_getsize, _mock_file, mock_sleep):
    mock_getsize.side_effect = [100, 100]

    assert wait_until_file_ready("photo.jpg", attempts=3, delay_seconds=0.01) is True
    assert mock_getsize.call_count == 2
    mock_sleep.assert_called_once_with(0.01)


@patch("src.observer.time.sleep")
@patch("builtins.open", new_callable=mock_open, read_data=b"x")
@patch("src.observer.os.path.getsize")
def test_wait_until_file_ready_retries_permission_errors(mock_getsize, _mock_file, mock_sleep):
    mock_getsize.side_effect = [PermissionError("locked"), 100, 100]

    assert wait_until_file_ready("photo.jpg", attempts=4, delay_seconds=0.01) is True
    assert mock_getsize.call_count == 3
    assert mock_sleep.call_count == 2
