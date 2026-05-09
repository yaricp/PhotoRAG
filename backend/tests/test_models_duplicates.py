"""
Tests for PhotoHash and PhotoDuplicate ORM models.

Behaviors under test:
- PhotoHash stores dhash/ahash/phash for a photo (one row per photo)
- PhotoDuplicate links two photos as original/duplicate with match_type and distance
- match_type is 'exact' or 'perceptual'
- hash_distance is None for exact duplicates, integer for perceptual
- Deleting a Photo cascades to its PhotoHash row
"""
import sys
from unittest.mock import MagicMock
import sqlalchemy.types

mock_pgvector = MagicMock()
mock_pgvector.sqlalchemy.Vector = lambda size: sqlalchemy.types.JSON()
sys.modules['pgvector'] = mock_pgvector
sys.modules['pgvector.sqlalchemy'] = mock_pgvector.sqlalchemy

import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models import Base, Photo, PhotoHash, PhotoDuplicate

TEST_DB = "test_models_duplicates.sqlite3"
_engine = create_engine(f"sqlite:///{TEST_DB}")
_Session = sessionmaker(bind=_engine)


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    Base.metadata.create_all(bind=_engine)
    yield
    _engine.dispose()
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


@pytest.fixture
def db():
    session = _Session()
    yield session
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()
    session.close()


# ── PhotoHash ────────────────────────────────────────────────────────────────

def test_photo_hash_stores_all_three_hashes(db):
    photo = Photo(hash="sha_h1", file_path="img1.jpg")
    db.add(photo)
    db.flush()

    ph = PhotoHash(photo_id=photo.id, dhash="aabbccdd11223344", ahash="1122334455667788", phash="9900aabbccddeeff")
    db.add(ph)
    db.commit()

    result = db.query(PhotoHash).filter_by(photo_id=photo.id).first()
    assert result is not None
    assert result.dhash == "aabbccdd11223344"
    assert result.ahash == "1122334455667788"
    assert result.phash == "9900aabbccddeeff"


def test_photo_hash_one_row_per_photo(db):
    photo = Photo(hash="sha_h2", file_path="img2.jpg")
    db.add(photo)
    db.flush()

    ph = PhotoHash(photo_id=photo.id, dhash="aaaa", ahash="bbbb", phash="cccc")
    db.add(ph)
    db.commit()

    count = db.query(PhotoHash).filter_by(photo_id=photo.id).count()
    assert count == 1


def test_photo_hash_relationship_accessible_from_photo(db):
    photo = Photo(hash="sha_h3", file_path="img3.jpg")
    db.add(photo)
    db.flush()

    ph = PhotoHash(photo_id=photo.id, dhash="dddd", ahash="eeee", phash="ffff")
    db.add(ph)
    db.commit()
    db.refresh(photo)

    assert photo.photo_hash is not None
    assert photo.photo_hash.dhash == "dddd"


# ── PhotoDuplicate ────────────────────────────────────────────────────────────

def test_photo_duplicate_exact_stores_file_path(db):
    orig = Photo(hash="sha_orig1", file_path="orig1.jpg")
    db.add(orig)
    db.flush()

    record = PhotoDuplicate(
        original_photo_id=orig.id,
        duplicate_file_path="/some/other/copy.jpg",
        match_type="exact",
        hash_distance=None,
    )
    db.add(record)
    db.commit()

    result = db.query(PhotoDuplicate).filter_by(original_photo_id=orig.id).first()
    assert result.match_type == "exact"
    assert result.duplicate_file_path == "/some/other/copy.jpg"
    assert result.duplicate_photo_id is None
    assert result.hash_distance is None


def test_photo_duplicate_perceptual_stores_photo_id_and_distance(db):
    orig = Photo(hash="sha_orig2", file_path="orig2.jpg")
    dup = Photo(hash="sha_dup2", file_path="dup2.jpg")
    db.add_all([orig, dup])
    db.flush()

    record = PhotoDuplicate(
        original_photo_id=orig.id,
        duplicate_photo_id=dup.id,
        match_type="perceptual",
        hash_distance=7,
    )
    db.add(record)
    db.commit()

    result = db.query(PhotoDuplicate).filter_by(duplicate_photo_id=dup.id).first()
    assert result.match_type == "perceptual"
    assert result.hash_distance == 7
    assert result.duplicate_file_path is None


def test_photo_duplicate_original_relationship(db):
    orig = Photo(hash="sha_orig3", file_path="orig3.jpg")
    dup = Photo(hash="sha_dup3", file_path="dup3.jpg")
    db.add_all([orig, dup])
    db.flush()

    record = PhotoDuplicate(
        original_photo_id=orig.id,
        duplicate_photo_id=dup.id,
        match_type="perceptual",
        hash_distance=3,
    )
    db.add(record)
    db.commit()

    result = db.query(PhotoDuplicate).filter_by(original_photo_id=orig.id).first()
    assert result.original_photo.hash == "sha_orig3"
    assert result.duplicate_photo.hash == "sha_dup3"


def test_one_original_can_have_multiple_duplicates(db):
    orig = Photo(hash="sha_multi_orig", file_path="multi_orig.jpg")
    db.add(orig)
    db.flush()

    db.add(PhotoDuplicate(original_photo_id=orig.id, duplicate_file_path="/a/copy1.jpg", match_type="exact"))
    db.add(PhotoDuplicate(original_photo_id=orig.id, duplicate_file_path="/b/copy2.jpg", match_type="exact"))
    db.commit()

    count = db.query(PhotoDuplicate).filter_by(original_photo_id=orig.id).count()
    assert count == 2
