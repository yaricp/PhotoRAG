# ATOMIC MOCK
import os
import sys
from unittest.mock import MagicMock, patch

import pytest
import sqlalchemy.orm
import sqlalchemy.types
from sqlalchemy import create_engine

from src.db_service import (
    check_photo_hash_exists,
    create_photo_record,
    get_all_model_configs,
    get_all_model_states,
    get_all_settings,
    get_model_config,
    get_or_create_camera,
    get_or_create_keyword,
    get_or_create_photo,
    init_default_model_configs,
    set_setting,
    update_model_config,
    update_model_status,
    update_photo_geoposition,
)
from src.models import Base
from src.schemas import AIModelConfigUpdate

TEST_DB_FILE = "test_db_service_final.sqlite3"
test_engine = create_engine(f"sqlite:///{TEST_DB_FILE}")


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    if os.path.exists(TEST_DB_FILE):
        os.remove(TEST_DB_FILE)
    Base.metadata.create_all(bind=test_engine)
    yield
    if os.path.exists(TEST_DB_FILE):
        os.remove(TEST_DB_FILE)


TestSessionLocal = sqlalchemy.orm.sessionmaker(bind=test_engine)


@pytest.fixture
def db_session():
    session = TestSessionLocal()
    yield session
    # Clear all tables for isolation
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()
    session.close()


@patch("src.db_service.generate_file_hash")
def test_photo_registration_flow(mock_hash, db_session):
    mock_hash.return_value = "hash1"

    # Test create_photo_record
    photo = create_photo_record(db_session, "hash1", "path1.jpg")
    assert photo.id is not None

    # Test check_photo_hash_exists
    exists = check_photo_hash_exists(db_session, "hash1")
    assert exists.id == photo.id

    # Test get_or_create_photo
    existing = get_or_create_photo(db_session, "path1.jpg")
    assert existing.id == photo.id
    assert mock_hash.called


def test_model_status_service(db_session):
    update_model_status(db_session, "test_model", "downloading")
    states = get_all_model_states(db_session)
    assert len(states) == 1
    assert states[0].status == "downloading"

    update_model_status(db_session, "test_model", "ready")
    assert states[0].status == "ready"


def test_semantic_upserts(db_session):
    # Test Camera Upsert
    cam1 = get_or_create_camera(db_session, "Sony", "A7")
    cam2 = get_or_create_camera(db_session, "Sony", "A7")
    assert cam1.id == cam2.id

    # Test Keyword Upsert
    kw1 = get_or_create_keyword(db_session, "forest")
    kw2 = get_or_create_keyword(db_session, "forest")
    assert kw1.id == kw2.id

    # Test Geoposition
    photo = create_photo_record(db_session, "geohash", "geo.jpg")
    geo = update_photo_geoposition(db_session, photo.id, 10.0, 20.0, "The Moon")
    assert geo.latitude == 10.0
    assert geo.address == "The Moon"


def test_model_configs_crud(db_session):
    # Test initialization
    init_default_model_configs(db_session)
    configs = get_all_model_configs(db_session)
    assert len(configs) >= 6

    # Test get by type
    vision_config = get_model_config(db_session, "vision")
    assert vision_config is not None
    assert vision_config.type == "vision"
    assert vision_config.mode == "local"

    # Test update
    update_schema = AIModelConfigUpdate(mode="remote", model_name="new-vision", url="http://api.com", api_key="123")
    updated = update_model_config(db_session, "vision", update_schema)
    assert updated.mode == "remote"
    assert updated.model_name == "new-vision"
    assert updated.url == "http://api.com"
    assert updated.api_key == "123"

    # Verify via get
    re_fetched = get_model_config(db_session, "vision")
    assert re_fetched.mode == "remote"
    assert re_fetched.url == "http://api.com"


def test_set_setting_creates_and_updates(db_session):
    result = set_setting(db_session, "default_language", "ru")
    assert result.key == "default_language"
    assert result.value == "ru"

    result2 = set_setting(db_session, "default_language", "es")
    assert result2.value == "es"

    settings = get_all_settings(db_session)
    assert settings["default_language"] == "es"


def test_set_setting_retries_on_locked_db(db_session):
    """set_setting must retry up to 3× on OperationalError: database is locked."""
    from unittest.mock import patch

    from sqlalchemy.exc import OperationalError

    locked_error = OperationalError("database is locked", None, None)
    call_count = 0

    original_commit = db_session.commit

    def flaky_commit():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise locked_error
        return original_commit()

    with patch.object(db_session, "commit", side_effect=flaky_commit):
        result = set_setting(db_session, "retry_key", "ok")

    assert result.value == "ok"
    assert call_count == 2  # failed once, succeeded on second attempt
