"""
TDD tests for template_tags and template_categories DB service functions.
All tests use an in-memory SQLite DB — no external dependencies.
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
    create_template_category,
    create_template_tag,
    delete_template_category,
    delete_template_tag,
    get_all_template_categories,
    get_all_template_categories_ordered,
    get_all_template_tags,
    get_all_template_tags_ordered,
    get_template_category_by_id,
    get_template_tag_by_id,
    update_template_category,
    update_template_tag,
)
from src.models import Base

TEST_DB = "test_template_service.sqlite3"
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


# ── TemplateTag ────────────────────────────────────────────────────────────────


class TestCreateTemplateTag:
    def test_creates_with_name_and_prompt(self, db):
        tag = create_template_tag(db, name="dog", clip_prompt="a photo of a dog")
        assert tag.id is not None
        assert tag.name == "dog"
        assert tag.clip_prompt == "a photo of a dog"

    def test_created_at_is_set(self, db):
        tag = create_template_tag(db, name="cat", clip_prompt="cat")
        assert tag.created_at is not None

    def test_duplicate_name_raises(self, db):
        create_template_tag(db, name="bird", clip_prompt="bird")
        with pytest.raises(Exception):
            create_template_tag(db, name="bird", clip_prompt="bird again")


class TestGetTemplateTag:
    def test_get_by_id_returns_correct_tag(self, db):
        tag = create_template_tag(db, name="car", clip_prompt="a car")
        fetched = get_template_tag_by_id(db, tag.id)
        assert fetched is not None
        assert fetched.name == "car"

    def test_get_by_id_returns_none_for_missing(self, db):
        result = get_template_tag_by_id(db, 999)
        assert result is None


class TestGetAllTemplateTags:
    def test_paginated_returns_correct_slice(self, db):
        for i in range(10):
            create_template_tag(db, name=f"tag_{i:02d}", clip_prompt=f"tag {i}")
        tags, total = get_all_template_tags(db, skip=0, limit=5)
        assert len(tags) == 5
        assert total == 10

    def test_skip_offsets_results(self, db):
        for i in range(6):
            create_template_tag(db, name=f"item_{i}", clip_prompt=f"item {i}")
        tags, total = get_all_template_tags(db, skip=4, limit=5)
        assert len(tags) == 2
        assert total == 6

    def test_empty_returns_zero(self, db):
        tags, total = get_all_template_tags(db, skip=0, limit=50)
        assert tags == []
        assert total == 0


class TestGetAllTemplateTagsOrdered:
    def test_ordered_by_id(self, db):
        t1 = create_template_tag(db, name="alpha", clip_prompt="alpha")
        t2 = create_template_tag(db, name="beta", clip_prompt="beta")
        t3 = create_template_tag(db, name="gamma", clip_prompt="gamma")
        ordered = get_all_template_tags_ordered(db)
        ids = [t.id for t in ordered]
        assert ids == sorted(ids)
        assert len(ordered) == 3


class TestUpdateTemplateTag:
    def test_update_name_and_prompt(self, db):
        tag = create_template_tag(db, name="old", clip_prompt="old prompt")
        updated = update_template_tag(db, tag.id, name="new", clip_prompt="new prompt")
        assert updated.name == "new"
        assert updated.clip_prompt == "new prompt"

    def test_update_nonexistent_returns_none(self, db):
        result = update_template_tag(db, 999, name="x", clip_prompt="x")
        assert result is None

    def test_updated_at_changes(self, db):
        import time

        tag = create_template_tag(db, name="ts_tag", clip_prompt="ts")
        before = tag.updated_at
        time.sleep(0.01)
        updated = update_template_tag(db, tag.id, name="ts_tag", clip_prompt="ts updated")
        assert updated.clip_prompt == "ts updated"


class TestDeleteTemplateTag:
    def test_delete_existing_returns_true(self, db):
        tag = create_template_tag(db, name="to_delete", clip_prompt="bye")
        result = delete_template_tag(db, tag.id)
        assert result is True
        assert get_template_tag_by_id(db, tag.id) is None

    def test_delete_nonexistent_returns_false(self, db):
        result = delete_template_tag(db, 99999)
        assert result is False


# ── TemplateCategory ───────────────────────────────────────────────────────────


class TestCreateTemplateCategory:
    def test_creates_with_name_and_prompt(self, db):
        cat = create_template_category(db, name="food", clip_prompt="a photo of food")
        assert cat.id is not None
        assert cat.name == "food"
        assert cat.clip_prompt == "a photo of food"

    def test_duplicate_name_raises(self, db):
        create_template_category(db, name="travel", clip_prompt="travel photo")
        with pytest.raises(Exception):
            create_template_category(db, name="travel", clip_prompt="another travel")


class TestGetTemplateCategory:
    def test_get_by_id(self, db):
        cat = create_template_category(db, name="nature", clip_prompt="nature scene")
        fetched = get_template_category_by_id(db, cat.id)
        assert fetched.name == "nature"

    def test_get_by_id_missing_returns_none(self, db):
        assert get_template_category_by_id(db, 9999) is None


class TestGetAllTemplateCategories:
    def test_paginated(self, db):
        for i in range(8):
            create_template_category(db, name=f"cat_{i}", clip_prompt=f"cat {i}")
        cats, total = get_all_template_categories(db, skip=0, limit=5)
        assert len(cats) == 5
        assert total == 8

    def test_empty(self, db):
        cats, total = get_all_template_categories(db, skip=0, limit=50)
        assert cats == []
        assert total == 0


class TestGetAllTemplateCategoriesOrdered:
    def test_ordered_by_id(self, db):
        create_template_category(db, name="c1", clip_prompt="c1")
        create_template_category(db, name="c2", clip_prompt="c2")
        ordered = get_all_template_categories_ordered(db)
        ids = [c.id for c in ordered]
        assert ids == sorted(ids)


class TestUpdateTemplateCategory:
    def test_update(self, db):
        cat = create_template_category(db, name="old_cat", clip_prompt="old")
        updated = update_template_category(db, cat.id, name="new_cat", clip_prompt="new")
        assert updated.name == "new_cat"
        assert updated.clip_prompt == "new"

    def test_update_nonexistent_returns_none(self, db):
        assert update_template_category(db, 9999, name="x", clip_prompt="x") is None


class TestDeleteTemplateCategory:
    def test_delete_existing(self, db):
        cat = create_template_category(db, name="del_cat", clip_prompt="del")
        assert delete_template_category(db, cat.id) is True
        assert get_template_category_by_id(db, cat.id) is None

    def test_delete_nonexistent(self, db):
        assert delete_template_category(db, 99999) is False
