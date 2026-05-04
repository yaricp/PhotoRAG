import pytest
from unittest.mock import MagicMock, patch
import os
from src.ai.ocr import extract_text_from_image, EasyOCRReader

@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the EasyOCRReader singleton before each test."""
    EasyOCRReader._instance = None
    yield
    EasyOCRReader._instance = None

def test_extract_text_easyocr_basic():
    """
    Test that the extraction function calls the EasyOCR reader.
    """
    with patch('easyocr.Reader') as mock_reader_class:
        mock_reader = mock_reader_class.return_value
        # EasyOCR returns list of strings when detail=0
        mock_reader.readtext.return_value = ['Hello World']
        
        result = extract_text_from_image("dummy.jpg", lang="en")
        assert "Hello World" in result
        mock_reader_class.assert_called_once_with(['en'], gpu=False)

def test_extract_text_easyocr_multilang():
    """
    Test that the extraction handles multiple languages.
    """
    with patch('easyocr.Reader') as mock_reader_class:
        mock_reader = mock_reader_class.return_value
        mock_reader.readtext.return_value = ['Привет', 'World']
        
        result = extract_text_from_image("dummy.jpg", lang="ru+en")
        assert "Привет" in result
        assert "World" in result
        mock_reader_class.assert_called_once_with(['ru', 'en'], gpu=False)

def test_extract_text_easyocr_error_handling():
    """
    Test that errors are handled gracefully.
    """
    # Reset singleton to ensure it tries to initialize
    EasyOCRReader._instance = None
    with patch('easyocr.Reader') as mock_reader_class:
        mock_reader = mock_reader_class.return_value
        mock_reader.readtext.side_effect = Exception("Read error")
        
        result = extract_text_from_image("broken.jpg")
        assert result == ""
