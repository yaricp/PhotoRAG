"""
TDD tests for photo-edit DB service functions.
Covers: trash flag, is_doc toggle, field update, tag/category manual link+unlink.
"""

import sys
from unittest.mock import MagicMock

import sqlalchemy.types

mock_pgvector = MagicMock()
mock_pgvector.sqlalchemy.Vector = lambda size: sqlalchemy.types.JSON()
sys.modules["pgvector"] = mock_pgvector
sys.modules["pgvector.sqlalchemy"] = mock_pgvector.sqlalchemy

import os

import pytest
import sqlalchemy.orm
from sqlalchemy import create_engine

from src.db_service import (
    get_photo_is_trash,
    link_photo_category,
    link_photo_tag,
    mark_photo_as_trash,
    set_photo_is_doc,
    unlink_photo_category,
    unlink_photo_tag,
    unmark_photo_as_trash,
    update_photo_fields,
)
from src.models import (
    Base,
    Category,
    Photo,
    PhotoCategory,
    PhotoQualityIssue,
    PhotoTag,
    Tag,
)

TEST_DB = "test_photo_edit_service.sqlite3"
engine = create_engine(f"sqlite:///{TEST_DB}")


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    Base.metadata.create_all(bind=engine)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


Session = sqlalchemy.orm.sessionmaker(bind=engine)


@pytest.fixture
def db():
    session = Session()
    yield session
    session.rollback()
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()
    session.close()


@pytest.fixture
def photo(db):
    p = Photo(file_path="/test/photo.jpg", description="test desc")
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


# ── Trash flag ────────────────────────────────────────────────────────────────


class TestTrashFlag:
    def test_photo_is_not_trash_by_default(self, db, photo):
        assert get_photo_is_trash(db, photo.id) is False

    def test_mark_photo_as_trash(self, db, photo):
        mark_photo_as_trash(db, photo.id)
        db.commit()
        assert get_photo_is_trash(db, photo.id) is True

    def test_mark_trash_idempotent(self, db, photo):
        mark_photo_as_trash(db, photo.id)
        mark_photo_as_trash(db, photo.id)
        db.commit()
        issues = db.query(PhotoQualityIssue).filter_by(photo_id=photo.id, issue_type="user_trash").all()
        assert len(issues) == 1

    def test_unmark_photo_removes_only_user_trash(self, db, photo):
        # Add both a user_trash and a legitimate issue
        db.add(PhotoQualityIssue(photo_id=photo.id, issue_type="user_trash"))
        db.add(PhotoQualityIssue(photo_id=photo.id, issue_type="no_exif"))
        db.commit()

        unmark_photo_as_trash(db, photo.id)
        db.commit()

        assert get_photo_is_trash(db, photo.id) is False
        # Legitimate issue must survive
        remaining = db.query(PhotoQualityIssue).filter_by(photo_id=photo.id).all()
        assert len(remaining) == 1
        assert remaining[0].issue_type == "no_exif"

    def test_unmark_trash_when_not_trash_is_safe(self, db, photo):
        unmark_photo_as_trash(db, photo.id)
        db.commit()
        assert get_photo_is_trash(db, photo.id) is False


# ── is_doc toggle ─────────────────────────────────────────────────────────────


class TestIsDoc:
    def test_set_is_doc_true(self, db, photo):
        result = set_photo_is_doc(db, photo.id, True)
        db.commit()
        assert result is not None
        assert result.is_doc is True

    def test_set_is_doc_false(self, db, photo):
        set_photo_is_doc(db, photo.id, True)
        db.commit()
        result = set_photo_is_doc(db, photo.id, False)
        db.commit()
        assert result.is_doc is False

    def test_set_is_doc_nonexistent_returns_none(self, db):
        result = set_photo_is_doc(db, 9999, True)
        assert result is None


# ── Field update ──────────────────────────────────────────────────────────────


class TestUpdatePhotoFields:
    def test_update_description(self, db, photo):
        result = update_photo_fields(db, photo.id, description="new desc")
        db.commit()
        assert result.description == "new desc"

    def test_update_translated_description(self, db, photo):
        result = update_photo_fields(db, photo.id, translated_description="перевод")
        db.commit()
        assert result.translated_description == "перевод"

    def test_update_ocr_text(self, db, photo):
        result = update_photo_fields(db, photo.id, ocr_text="extracted text")
        db.commit()
        assert result.ocr_text == "extracted text"

    def test_partial_update_leaves_other_fields_unchanged(self, db, photo):
        update_photo_fields(db, photo.id, description="A")
        db.commit()
        result = update_photo_fields(db, photo.id, ocr_text="B")
        db.commit()
        assert result.description == "A"
        assert result.ocr_text == "B"

    def test_update_nonexistent_returns_none(self, db):
        result = update_photo_fields(db, 9999, description="x")
        assert result is None


# ── Tag link / unlink ─────────────────────────────────────────────────────────


class TestPhotoTagLink:
    def test_link_creates_tag_if_missing(self, db, photo):
        pt = link_photo_tag(db, photo.id, "sunset")
        db.commit()
        assert pt is not None
        assert pt.tag.name == "sunset"
        assert pt.confidence_score == 1.0

    def test_link_tag_idempotent(self, db, photo):
        link_photo_tag(db, photo.id, "sunset")
        db.commit()
        link_photo_tag(db, photo.id, "sunset")
        db.commit()
        rows = db.query(PhotoTag).filter_by(photo_id=photo.id).all()
        assert len(rows) == 1

    def test_link_reuses_existing_tag(self, db, photo):
        existing = Tag(name="mountain")
        db.add(existing)
        db.commit()
        pt = link_photo_tag(db, photo.id, "mountain")
        db.commit()
        assert pt.tag_id == existing.id

    def test_unlink_photo_tag(self, db, photo):
        pt = link_photo_tag(db, photo.id, "river")
        db.commit()
        tag_id = pt.tag_id
        result = unlink_photo_tag(db, photo.id, tag_id)
        db.commit()
        assert result is True
        assert db.query(PhotoTag).filter_by(photo_id=photo.id, tag_id=tag_id).first() is None

    def test_unlink_tag_not_linked_returns_false(self, db, photo):
        result = unlink_photo_tag(db, photo.id, 9999)
        assert result is False


# ── Category link / unlink ────────────────────────────────────────────────────


class TestPhotoCategoryLink:
    def test_link_creates_category_if_missing(self, db, photo):
        pc = link_photo_category(db, photo.id, "nature")
        db.commit()
        assert pc is not None
        assert pc.category.name == "nature"
        assert pc.confidence_score == 1.0

    def test_link_category_idempotent(self, db, photo):
        link_photo_category(db, photo.id, "nature")
        db.commit()
        link_photo_category(db, photo.id, "nature")
        db.commit()
        rows = db.query(PhotoCategory).filter_by(photo_id=photo.id).all()
        assert len(rows) == 1

    def test_link_reuses_existing_category(self, db, photo):
        existing = Category(name="travel", prompt="travel")
        db.add(existing)
        db.commit()
        pc = link_photo_category(db, photo.id, "travel")
        db.commit()
        assert pc.category_id == existing.id

    def test_unlink_photo_category(self, db, photo):
        pc = link_photo_category(db, photo.id, "food")
        db.commit()
        cat_id = pc.category_id
        result = unlink_photo_category(db, photo.id, cat_id)
        db.commit()
        assert result is True
        assert db.query(PhotoCategory).filter_by(photo_id=photo.id, category_id=cat_id).first() is None

    def test_unlink_category_not_linked_returns_false(self, db, photo):
        result = unlink_photo_category(db, photo.id, 9999)
        assert result is False
