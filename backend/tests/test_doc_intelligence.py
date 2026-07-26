import sys
from unittest.mock import MagicMock, patch

import pytest

from src.models import Photo
from src.tasks.vision_tasks import is_this_document_task, ocr_task

# MOCK setup


@pytest.fixture
def mock_db():
    db = MagicMock()
    return db


@patch("src.tasks.vision_tasks.registry")
@patch("src.tasks.vision_tasks.SessionLocal")
def test_is_this_document_logic_yes(mock_session, mock_registry, mock_db):
    mock_session.return_value = mock_db
    photo = Photo(id=1, file_path="doc.jpg", is_doc=False)
    mock_db.query.return_value.filter.return_value.first.return_value = photo

    # Mock Vision generator returning "Yes"
    mock_registry.generate_vision_text.return_value = "Yes, this is a document."

    is_this_document_task.call_local(1, phase="test_phase")

    assert photo.is_doc is True
    mock_db.commit.assert_called()


@patch("src.tasks.vision_tasks.registry")
@patch("src.tasks.vision_tasks.SessionLocal")
def test_is_this_document_logic_no(mock_session, mock_registry, mock_db):
    mock_session.return_value = mock_db
    photo = Photo(id=1, file_path="cat.jpg", is_doc=False)
    mock_db.query.return_value.filter.return_value.first.return_value = photo

    mock_registry.generate_vision_text.return_value = "No, this is a cat."

    is_this_document_task.call_local(1, phase="test_phase")

    assert photo.is_doc is False


@patch("src.tasks.vision_tasks.is_this_document_task")
@patch("src.tasks.vision_tasks.extract_text_from_image")
@patch("src.tasks.vision_tasks.SessionLocal")
def test_ocr_triggers_doc_check_when_text_found(mock_session, mock_ocr, mock_doc_task, mock_db):
    mock_session.return_value = mock_db
    photo = Photo(id=1, file_path="doc.jpg")
    mock_db.query.return_value.filter.return_value.first.return_value = photo

    mock_ocr.return_value = "Invoice #123"

    ocr_task.call_local(1, phase="test_phase")

    mock_doc_task.assert_called_once_with(1, "test_phase")
