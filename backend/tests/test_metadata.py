from src.metadata import get_exif_data
from unittest.mock import patch, MagicMock

def test_get_exif_data_basic():
    # Use a mock for the file to avoid needing a real photo in the tests
    with patch('builtins.open', MagicMock()), \
         patch('exifread.process_file', return_value={
             'Image Model': 'Pixel 6',
             'Image DateTime': '2024:01:01 12:00:00'
         }):
        data = get_exif_data("dummy.jpg")
        assert data["model"] == "Pixel 6"
        assert data["datetime"] == "2024:01:01 12:00:00"
