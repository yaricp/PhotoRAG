"""
Tests for db_service duplicate helper functions.

Behaviors under test:
- record_exact_duplicate(db, original_id, duplicate_photo_id) creates PhotoDuplicate row
- record_exact_duplicate is idempotent (same pair twice → one row)
- get_or_create_photo_hash creates a row on first call, returns same on second call
- find_perceptual_duplicates returns photo_ids whose hashes are within threshold
- find_perceptual_duplicates does NOT return photos outside the threshold
- get_duplicate_groups returns the correct grouped structure for the API
"""

import os
import sys
from unittest.mock import MagicMock

import pytest
import sqlalchemy.types
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.db_service import (
    create_photo_record,
    find_perceptual_duplicates,
    get_duplicate_groups,
    get_or_create_photo_hash,
    record_exact_duplicate,
)
from src.models import Base, PhotoDuplicate, PhotoHash

TEST_DB = "test_db_service_duplicates.sqlite3"
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


# ── record_exact_duplicate ────────────────────────────────────────────────────


def test_record_exact_duplicate_creates_row(db):
    orig = create_photo_record(db, "hash_re_orig", "re_orig.jpg")

    record_exact_duplicate(db, orig.id, "/copies/re_dup.jpg")

    row = (
        db.query(PhotoDuplicate)
        .filter_by(
            original_photo_id=orig.id,
            duplicate_file_path="/copies/re_dup.jpg",
        )
        .first()
    )
    assert row is not None
    assert row.match_type == "exact"
    assert row.hash_distance is None
    assert row.duplicate_photo_id is None


def test_record_exact_duplicate_is_idempotent(db):
    orig = create_photo_record(db, "hash_idem_orig", "idem_orig.jpg")

    record_exact_duplicate(db, orig.id, "/copies/idem_dup.jpg")
    record_exact_duplicate(db, orig.id, "/copies/idem_dup.jpg")

    count = (
        db.query(PhotoDuplicate)
        .filter_by(
            original_photo_id=orig.id,
            duplicate_file_path="/copies/idem_dup.jpg",
        )
        .count()
    )
    assert count == 1


# ── get_or_create_photo_hash ──────────────────────────────────────────────────


def test_get_or_create_photo_hash_creates_row(db):
    photo = create_photo_record(db, "hash_ph_new", "ph_new.jpg")

    ph = get_or_create_photo_hash(db, photo.id, dhash="aaaa", ahash="bbbb", phash="cccc")

    assert ph is not None
    assert ph.photo_id == photo.id
    assert ph.dhash == "aaaa"


def test_get_or_create_photo_hash_returns_existing(db):
    photo = create_photo_record(db, "hash_ph_exist", "ph_exist.jpg")

    ph1 = get_or_create_photo_hash(db, photo.id, dhash="1111", ahash="2222", phash="3333")
    ph2 = get_or_create_photo_hash(db, photo.id, dhash="1111", ahash="2222", phash="3333")

    assert ph1.id == ph2.id
    assert db.query(PhotoHash).filter_by(photo_id=photo.id).count() == 1


# ── find_perceptual_duplicates ─────────────────────────────────────────────────


def _hex_hash(n: int) -> str:
    """Build a 16-char hex string with n bits set (simple test fixture)."""
    val = (1 << n) - 1  # n lowest bits set
    return f"{val:016x}"


def test_find_perceptual_duplicates_returns_close_photos(db):
    photo_a = create_photo_record(db, "hash_pa", "pa.jpg")
    photo_b = create_photo_record(db, "hash_pb", "pb.jpg")

    # Both have the same hash → distance 0
    get_or_create_photo_hash(db, photo_a.id, dhash="0000000000000000", ahash="0", phash="0")
    get_or_create_photo_hash(db, photo_b.id, dhash="0000000000000001", ahash="0", phash="0")

    results = find_perceptual_duplicates(db, photo_a.id, threshold=10)

    assert photo_b.id in [r["photo_id"] for r in results]


def test_find_perceptual_duplicates_excludes_distant_photos(db):
    photo_a = create_photo_record(db, "hash_dist_a", "dist_a.jpg")
    photo_b = create_photo_record(db, "hash_dist_b", "dist_b.jpg")

    # distance > 10: photo_b has 11 bits different from photo_a
    get_or_create_photo_hash(db, photo_a.id, dhash="0000000000000000", ahash="0", phash="0")
    get_or_create_photo_hash(db, photo_b.id, dhash="00000000000007ff", ahash="0", phash="0")  # 11 bits set

    results = find_perceptual_duplicates(db, photo_a.id, threshold=10)

    assert photo_b.id not in [r["photo_id"] for r in results]


def test_find_perceptual_duplicates_does_not_return_self(db):
    photo = create_photo_record(db, "hash_self", "self.jpg")
    get_or_create_photo_hash(db, photo.id, dhash="0000000000000000", ahash="0", phash="0")

    results = find_perceptual_duplicates(db, photo.id, threshold=10)

    assert photo.id not in [r["photo_id"] for r in results]


# ── get_duplicate_groups ──────────────────────────────────────────────────────


def test_get_duplicate_groups_returns_exact_and_perceptual_sections(db):
    orig = create_photo_record(db, "hash_grp_orig", "grp_orig.jpg")
    dup_perc = create_photo_record(db, "hash_grp_perc", "grp_perc.jpg")

    db.add(PhotoDuplicate(original_photo_id=orig.id, duplicate_file_path="/dup/exact.jpg", match_type="exact"))
    db.add(
        PhotoDuplicate(
            original_photo_id=orig.id, duplicate_photo_id=dup_perc.id, match_type="perceptual", hash_distance=5
        )
    )
    db.commit()

    groups = get_duplicate_groups(db)

    assert "exact" in groups
    assert "perceptual" in groups


def test_get_duplicate_groups_exact_contains_correct_original(db):
    orig = create_photo_record(db, "hash_go_orig", "go_orig.jpg")

    db.add(PhotoDuplicate(original_photo_id=orig.id, duplicate_file_path="/dup/go.jpg", match_type="exact"))
    db.commit()

    groups = get_duplicate_groups(db)

    exact_originals = [g["original"]["id"] for g in groups["exact"]]
    assert orig.id in exact_originals


def test_get_duplicate_groups_exact_contains_duplicate_file_path(db):
    orig = create_photo_record(db, "hash_gfp_orig", "gfp_orig.jpg")

    db.add(PhotoDuplicate(original_photo_id=orig.id, duplicate_file_path="/dup/gfp.jpg", match_type="exact"))
    db.commit()

    groups = get_duplicate_groups(db)

    group = next(g for g in groups["exact"] if g["original"]["id"] == orig.id)
    assert group["duplicates"][0]["file_path"] == "/dup/gfp.jpg"


def test_get_duplicate_groups_perceptual_contains_distance(db):
    orig = create_photo_record(db, "hash_gp_orig", "gp_orig.jpg")
    dup = create_photo_record(db, "hash_gp_dup", "gp_dup.jpg")

    db.add(
        PhotoDuplicate(original_photo_id=orig.id, duplicate_photo_id=dup.id, match_type="perceptual", hash_distance=8)
    )
    db.commit()

    groups = get_duplicate_groups(db)

    perc_group = next(g for g in groups["perceptual"] if g["original"]["id"] == orig.id)
    assert perc_group["duplicates"][0]["hash_distance"] == 8
