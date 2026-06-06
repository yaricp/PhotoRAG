"""
Tests for geoposition deduplication and coordinate rounding.

Behaviors under test:
- lat/lon are rounded to 3 decimal places before storage
- two photos at the same rounded location share one Geoposition row
- different address at same coordinates creates a separate row
- photo.geoposition_id is set after update
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
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.db_service import create_photo_record, update_photo_geoposition
from src.models import Base, Geoposition

TEST_DB = "test_geoposition.sqlite3"
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
    session.rollback()
    session.close()


# ── Rounding ────────────────────────────────────────────────────────────────


def test_latitude_rounded_to_3_decimal_places(db):
    photo = create_photo_record(db, "hash_round_lat", "round_lat.jpg")
    geo = update_photo_geoposition(db, photo.id, 48.123456, 11.0, "City A")
    assert geo.latitude == 48.123


def test_longitude_rounded_to_3_decimal_places(db):
    photo = create_photo_record(db, "hash_round_lon", "round_lon.jpg")
    geo = update_photo_geoposition(db, photo.id, 10.0, 11.567891, "City B")
    assert geo.longitude == 11.568


def test_negative_coordinates_rounded(db):
    photo = create_photo_record(db, "hash_neg", "neg.jpg")
    geo = update_photo_geoposition(db, photo.id, -33.86789, -70.64321, "Santiago")
    assert geo.latitude == -33.868
    assert geo.longitude == -70.643


# ── Photo linking ────────────────────────────────────────────────────────────


def test_photo_geoposition_id_is_set_after_update(db):
    photo = create_photo_record(db, "hash_link", "link.jpg")
    geo = update_photo_geoposition(db, photo.id, 48.0, 11.0, "Somewhere")
    db.refresh(photo)
    assert photo.geoposition_id == geo.id


def test_photo_geoposition_relationship_is_accessible(db):
    photo = create_photo_record(db, "hash_rel", "rel.jpg")
    update_photo_geoposition(db, photo.id, 52.0, 13.0, "Berlin")
    db.refresh(photo)
    assert photo.geoposition is not None
    assert photo.geoposition.address == "Berlin"


# ── Deduplication ────────────────────────────────────────────────────────────


def test_two_photos_at_same_location_share_one_geoposition_row(db):
    photo1 = create_photo_record(db, "hash_dedup1", "dedup1.jpg")
    photo2 = create_photo_record(db, "hash_dedup2", "dedup2.jpg")

    geo1 = update_photo_geoposition(db, photo1.id, 48.123, 11.567, "Munich")
    geo2 = update_photo_geoposition(db, photo2.id, 48.123, 11.567, "Munich")

    assert geo1.id == geo2.id


def test_coordinates_that_round_to_same_value_share_one_row(db):
    photo1 = create_photo_record(db, "hash_rdup1", "rdup1.jpg")
    photo2 = create_photo_record(db, "hash_rdup2", "rdup2.jpg")

    # 48.1234 and 48.1235 both round to 48.123
    geo1 = update_photo_geoposition(db, photo1.id, 48.1234, 11.0, "Rounded City")
    geo2 = update_photo_geoposition(db, photo2.id, 48.1235, 11.0, "Rounded City")

    assert geo1.id == geo2.id


def test_same_coordinates_different_address_creates_separate_row(db):
    photo1 = create_photo_record(db, "hash_diff1", "diff1.jpg")
    photo2 = create_photo_record(db, "hash_diff2", "diff2.jpg")

    geo1 = update_photo_geoposition(db, photo1.id, 40.0, 9.0, "Address One")
    geo2 = update_photo_geoposition(db, photo2.id, 40.0, 9.0, "Address Two")

    assert geo1.id != geo2.id


def test_dedup_does_not_create_extra_geoposition_rows(db):
    before = db.query(Geoposition).count()

    photo1 = create_photo_record(db, "hash_count1", "count1.jpg")
    photo2 = create_photo_record(db, "hash_count2", "count2.jpg")
    update_photo_geoposition(db, photo1.id, 55.0, 37.0, "Moscow")
    update_photo_geoposition(db, photo2.id, 55.0, 37.0, "Moscow")

    after = db.query(Geoposition).count()
    assert after == before + 1  # only one new row, not two
