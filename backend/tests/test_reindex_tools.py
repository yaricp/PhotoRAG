"""
Tests for reindex_photos and rerun_pipeline_for_photos agent tools.
Written before implementation (TDD).
"""

import sys
from unittest.mock import MagicMock, patch

import sqlalchemy.types

# Mock heavy deps before any src import

for _mod in [
    "sqlite_vec",
    "langgraph",
    "langgraph.graph",
    "src.database",
    "src.vector_db_services",
    "src.ai.registry",
    "src.ai.translator",
    "src.queues.folder_scan_queue",
    "src.queues.clip_queue",
    "src.queues.vision_queue",
    "src.queues.embedding_queue",
    "src.queues.translation_queue",
    "src.queues.queue_config",
    "src.tasks",
    "src.tasks.utils",
    "src.tasks.folder_scanners",
    "src.tasks.vision_tasks",
    "src.tasks.embedding_tasks",
    "src.tasks.clip_tasks",
    "src.tasks.translation_tasks",
    "src.model_services",
    "src.deps",
]:
    sys.modules.setdefault(_mod, MagicMock())

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models import Base, Category, PhotoCategory, PhotoTag, Tag
from src.models import Photo as PhotoModel


@pytest.fixture
def db_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session


@pytest.fixture
def db(db_factory):
    session = db_factory()
    yield session
    session.close()


@pytest.fixture
def photo_with_tags(db):
    p = PhotoModel(hash="tool_h1", file_path="/t/1.jpg", description="A lake")
    db.add(p)
    db.flush()
    t = Tag(name="nature")
    db.add(t)
    db.flush()
    c = Category(name="Landscape")
    db.add(c)
    db.flush()
    db.add(PhotoTag(photo_id=p.id, tag_id=t.id, confidence_score=0.9))
    db.add(PhotoCategory(photo_id=p.id, category_id=c.id, confidence_score=0.8))
    db.commit()
    return p


# ---------------------------------------------------------------------------
# reindex_photos
# ---------------------------------------------------------------------------


class TestReindexPhotosTool:
    def test_returns_started_message_for_valid_ids(self, db_factory, photo_with_tags):
        with patch("src.graphs.tools.SessionLocal", side_effect=db_factory), patch("threading.Thread") as mock_thread:
            from src.graphs.tools import reindex_photos

            result = reindex_photos.invoke({"photo_ids": [photo_with_tags.id]})

        assert "1 photo" in result
        mock_thread.return_value.start.assert_called_once()

    def test_returns_error_for_unknown_id(self, db_factory):
        with patch("src.graphs.tools.SessionLocal", side_effect=db_factory), patch("threading.Thread") as mock_thread:
            from src.graphs.tools import reindex_photos

            result = reindex_photos.invoke({"photo_ids": [99999]})

        assert "99999" in result
        assert "not found" in result.lower()
        mock_thread.return_value.start.assert_not_called()

    def test_returns_message_for_empty_list(self, db_factory):
        with patch("src.graphs.tools.SessionLocal", side_effect=db_factory):
            from src.graphs.tools import reindex_photos

            result = reindex_photos.invoke({"photo_ids": []})

        assert "no photo" in result.lower()

    def test_aborts_on_first_unknown_id_in_batch(self, db_factory, photo_with_tags):
        with patch("src.graphs.tools.SessionLocal", side_effect=db_factory), patch("threading.Thread") as mock_thread:
            from src.graphs.tools import reindex_photos

            result = reindex_photos.invoke({"photo_ids": [photo_with_tags.id, 99999]})

        assert "not found" in result.lower()
        mock_thread.return_value.start.assert_not_called()


# ---------------------------------------------------------------------------
# rerun_pipeline_for_photos
# ---------------------------------------------------------------------------


class TestRerunPipelineTool:
    def test_returns_started_message_for_valid_ids(self, db_factory, photo_with_tags):
        with patch("src.graphs.tools.SessionLocal", side_effect=db_factory), patch("threading.Thread") as mock_thread:
            from src.graphs.tools import rerun_pipeline_for_photos

            result = rerun_pipeline_for_photos.invoke({"photo_ids": [photo_with_tags.id]})

        assert "1 photo" in result
        mock_thread.return_value.start.assert_called_once()

    def test_returns_error_for_unknown_id(self, db_factory):
        with patch("src.graphs.tools.SessionLocal", side_effect=db_factory), patch("threading.Thread") as mock_thread:
            from src.graphs.tools import rerun_pipeline_for_photos

            result = rerun_pipeline_for_photos.invoke({"photo_ids": [99999]})

        assert "99999" in result
        assert "not found" in result.lower()
        mock_thread.return_value.start.assert_not_called()

    def test_clears_tags_and_categories_before_pipeline(self, db_factory, photo_with_tags):
        db = db_factory()
        assert db.query(PhotoTag).filter_by(photo_id=photo_with_tags.id).count() == 1
        assert db.query(PhotoCategory).filter_by(photo_id=photo_with_tags.id).count() == 1
        db.close()

        with patch("src.graphs.tools.SessionLocal", side_effect=db_factory), patch("threading.Thread"):
            from src.graphs.tools import rerun_pipeline_for_photos

            rerun_pipeline_for_photos.invoke({"photo_ids": [photo_with_tags.id]})

        db = db_factory()
        assert db.query(PhotoTag).filter_by(photo_id=photo_with_tags.id).count() == 0
        assert db.query(PhotoCategory).filter_by(photo_id=photo_with_tags.id).count() == 0
        db.close()

    def test_returns_message_for_empty_list(self, db_factory):
        with patch("src.graphs.tools.SessionLocal", side_effect=db_factory):
            from src.graphs.tools import rerun_pipeline_for_photos

            result = rerun_pipeline_for_photos.invoke({"photo_ids": []})

        assert "no photo" in result.lower()
