# backend/tests/test_tool_annotation.py
import sys
from unittest.mock import MagicMock, patch
import sqlalchemy.types

mock_pgvector = MagicMock()
mock_pgvector.sqlalchemy.Vector = lambda size: sqlalchemy.types.JSON()
sys.modules['pgvector'] = mock_pgvector
sys.modules['pgvector.sqlalchemy'] = mock_pgvector.sqlalchemy

for _mod in [
    'sqlite_vec', 'langgraph', 'langgraph.graph',
    'src.database', 'src.vector_db_services', 'src.config',
    'src.ai', 'src.ai.registry', 'src.ai.prompts', 'src.ai.translator',
    'src.graphs.ai_agent',
    'src.queues', 'src.queues.folder_scan_queue', 'src.queues.clip_queue',
    'src.queues.vision_queue', 'src.queues.embedding_queue',
    'src.queues.translation_queue',
    'src.tasks', 'src.tasks.utils', 'src.tasks.folder_scanners',
    'src.tasks.vision_tasks', 'src.tasks.embedding_tasks',
    'src.tasks.clip_tasks', 'src.tasks.translation_tasks',
    'src.deps',
    # geopy is not installed in the test environment
    'geopy', 'geopy.geocoders', 'geopy.exc',
    # exifread is not installed in the test environment
    'exifread',
]:
    sys.modules[_mod] = MagicMock()

import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models import Base, Photo as PhotoModel, Tag, PhotoTag, Category, PhotoCategory, Geoposition
from src.db_service import get_last_history_action


@pytest.fixture
def db_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    yield Session


@pytest.fixture
def db(db_factory):
    session = db_factory()
    yield session
    session.close()


def _make_photo(db, tmp_path, filename="photo.jpg"):
    f = tmp_path / filename
    f.write_bytes(b"imgdata")
    photo = PhotoModel(hash=filename, file_path=str(f))
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return photo


# ---------------------------------------------------------------------------
# add_tag_to_photos
# ---------------------------------------------------------------------------

def test_add_tag_creates_tag_and_links_photo(tmp_path, db, db_factory):
    from src.graphs.tools import add_tag_to_photos
    photo = _make_photo(db, tmp_path)

    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory):
        result = add_tag_to_photos.invoke({"photo_ids": [photo.id], "tag_name": "sunset"})

    assert "sunset" in result
    session = db_factory()
    tag = session.query(Tag).filter_by(name="sunset").first()
    assert tag is not None
    link = session.query(PhotoTag).filter_by(photo_id=photo.id, tag_id=tag.id).first()
    assert link is not None


def test_add_tag_saves_history_action(tmp_path, db, db_factory):
    from src.graphs.tools import add_tag_to_photos
    photo = _make_photo(db, tmp_path, "t2.jpg")

    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory):
        add_tag_to_photos.invoke({"photo_ids": [photo.id], "tag_name": "nature"})

    action = get_last_history_action(db_factory())
    assert action is not None
    assert action.action_type == "add_tag"


def test_add_tag_skips_missing_photo_id(db_factory):
    from src.graphs.tools import add_tag_to_photos
    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory):
        result = add_tag_to_photos.invoke({"photo_ids": [9999], "tag_name": "sky"})
    assert "0" in result or "Skipped" in result


def test_add_tag_undo_removes_link(tmp_path, db, db_factory):
    from src.graphs.tools import add_tag_to_photos, undo_last_action
    photo = _make_photo(db, tmp_path, "undo_tag.jpg")

    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory):
        add_tag_to_photos.invoke({"photo_ids": [photo.id], "tag_name": "temp"})

    session = db_factory()
    tag = session.query(Tag).filter_by(name="temp").first()
    link_before = session.query(PhotoTag).filter_by(photo_id=photo.id, tag_id=tag.id).first()
    assert link_before is not None

    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory):
        undo_last_action.invoke({})

    session2 = db_factory()
    link_after = session2.query(PhotoTag).filter_by(photo_id=photo.id, tag_id=tag.id).first()
    assert link_after is None


# ---------------------------------------------------------------------------
# add_category_to_photos
# ---------------------------------------------------------------------------

def test_add_category_creates_and_links(tmp_path, db, db_factory):
    from src.graphs.tools import add_category_to_photos
    photo = _make_photo(db, tmp_path, "cat.jpg")

    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory):
        result = add_category_to_photos.invoke({"photo_ids": [photo.id], "category_name": "Travel"})

    assert "Travel" in result
    session = db_factory()
    cat = session.query(Category).filter_by(name="Travel").first()
    assert cat is not None
    link = session.query(PhotoCategory).filter_by(photo_id=photo.id, category_id=cat.id).first()
    assert link is not None


def test_add_category_saves_history(tmp_path, db, db_factory):
    from src.graphs.tools import add_category_to_photos
    photo = _make_photo(db, tmp_path, "cat2.jpg")

    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory):
        add_category_to_photos.invoke({"photo_ids": [photo.id], "category_name": "Food"})

    action = get_last_history_action(db_factory())
    assert action.action_type == "add_category"


def test_add_category_undo_removes_link(tmp_path, db, db_factory):
    from src.graphs.tools import add_category_to_photos, undo_last_action
    photo = _make_photo(db, tmp_path, "undo_cat.jpg")

    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory):
        add_category_to_photos.invoke({"photo_ids": [photo.id], "category_name": "TempCat"})

    session = db_factory()
    cat = session.query(Category).filter_by(name="TempCat").first()

    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory):
        undo_last_action.invoke({})

    session2 = db_factory()
    link = session2.query(PhotoCategory).filter_by(photo_id=photo.id, category_id=cat.id).first()
    assert link is None


# ---------------------------------------------------------------------------
# add_geoposition_to_photos
# ---------------------------------------------------------------------------

def _make_mock_geo(lat=48.8566, lon=2.3522, address="Paris, France"):
    mock_geo = MagicMock()
    mock_loc = MagicMock()
    mock_loc.latitude = lat
    mock_loc.longitude = lon
    mock_loc.address = address
    mock_geo.return_value.geolocator.geocode.return_value = mock_loc
    mock_geo.return_value.reverse_geocode.return_value = address
    return mock_geo


def test_add_geoposition_by_lat_lon(tmp_path, db, db_factory):
    from src.graphs.tools import add_geoposition_to_photos
    photo = _make_photo(db, tmp_path, "geo.jpg")
    mock_enricher = MagicMock()
    mock_enricher.reverse_geocode.return_value = "Paris, France"

    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory), \
         patch("src.geo.GeoEnricher", return_value=mock_enricher):
        result = add_geoposition_to_photos.invoke({
            "photo_ids": [photo.id], "latitude": 48.8566, "longitude": 2.3522
        })

    assert "Paris" in result or "48.85" in result


def test_add_geoposition_by_address(tmp_path, db, db_factory):
    from src.graphs.tools import add_geoposition_to_photos
    photo = _make_photo(db, tmp_path, "geo2.jpg")
    mock_loc = MagicMock()
    mock_loc.latitude = 55.7558
    mock_loc.longitude = 37.6173
    mock_loc.address = "Moscow, Russia"
    mock_enricher = MagicMock()
    mock_enricher.geolocator.geocode.return_value = mock_loc
    mock_enricher.reverse_geocode.return_value = "Moscow, Russia"

    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory), \
         patch("src.geo.GeoEnricher", return_value=mock_enricher):
        result = add_geoposition_to_photos.invoke({
            "photo_ids": [photo.id], "address": "Moscow"
        })

    assert "Moscow" in result or "55.75" in result


def test_add_geoposition_saves_history(tmp_path, db, db_factory):
    from src.graphs.tools import add_geoposition_to_photos
    photo = _make_photo(db, tmp_path, "geo3.jpg")
    mock_enricher = MagicMock()
    mock_enricher.reverse_geocode.return_value = "Berlin, Germany"

    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory), \
         patch("src.geo.GeoEnricher", return_value=mock_enricher):
        add_geoposition_to_photos.invoke({
            "photo_ids": [photo.id], "latitude": 52.52, "longitude": 13.405
        })

    action = get_last_history_action(db_factory())
    assert action.action_type == "add_geoposition"


def test_add_geoposition_requires_lat_lon_or_address(db_factory):
    from src.graphs.tools import add_geoposition_to_photos
    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory):
        result = add_geoposition_to_photos.invoke({"photo_ids": [1]})
    assert "Error" in result


# ---------------------------------------------------------------------------
# geocode_photo_from_exif
# ---------------------------------------------------------------------------

def test_geocode_from_exif_saves_location(tmp_path, db, db_factory):
    from src.graphs.tools import geocode_photo_from_exif
    photo = _make_photo(db, tmp_path, "exif_geo.jpg")
    mock_enricher = MagicMock()
    mock_enricher.geocode_photo.return_value = {
        "latitude": 48.85, "longitude": 2.35, "address": "Paris"
    }

    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory), \
         patch("src.geo.GeoEnricher", return_value=mock_enricher), \
         patch("src.metadata.get_exif_data", return_value={}):
        result = geocode_photo_from_exif.invoke({"photo_id": photo.id})

    assert "48.85" in result or "Paris" in result


def test_geocode_from_exif_returns_error_when_no_gps(tmp_path, db, db_factory):
    from src.graphs.tools import geocode_photo_from_exif
    photo = _make_photo(db, tmp_path, "no_gps.jpg")
    mock_enricher = MagicMock()
    mock_enricher.geocode_photo.return_value = {
        "latitude": None, "longitude": None, "address": None
    }

    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory), \
         patch("src.geo.GeoEnricher", return_value=mock_enricher), \
         patch("src.metadata.get_exif_data", return_value={}):
        result = geocode_photo_from_exif.invoke({"photo_id": photo.id})

    assert "no GPS" in result or "Error" in result


def test_geocode_from_exif_not_found(db_factory):
    from src.graphs.tools import geocode_photo_from_exif
    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory):
        result = geocode_photo_from_exif.invoke({"photo_id": 9999})
    assert "not found" in result.lower()
