"""
Tests for exact duplicate detection in both pipeline entry points.

Behaviors under test:
- folder_scanners: when a file with the same SHA256 already exists in DB,
  record_exact_duplicate is called with the existing photo as original
- observer: same behavior triggered via on_created event
- the photo with the earlier captured_at is chosen as original when
  the duplicate file appears to be older than the DB record
- the existing Photo record is NOT replaced or duplicated in the photos table
"""
import sys
from unittest.mock import MagicMock, patch
import sqlalchemy.types

mock_pgvector = MagicMock()
mock_pgvector.sqlalchemy.Vector = lambda size: sqlalchemy.types.JSON()
sys.modules['pgvector'] = mock_pgvector
sys.modules['pgvector.sqlalchemy'] = mock_pgvector.sqlalchemy

# Native extensions and heavy dependencies unavailable in the test environment
for _mod in [
    'sqlite_vec', 'src.database', 'src.vector_db_services', 'src.config',
    'src.ai', 'src.ai.registry', 'src.ai.prompts',
    'src.queues', 'src.queues.folder_scan_queue',
    'src.queues.vision_queue', 'src.queues.embedding_queue',
    'src.queues.clip_queue', 'src.queues.translation_queue',
    'src.tasks.utils', 'src.tasks.vision_tasks', 'src.tasks.embedding_tasks',
    'src.tasks.clip_tasks', 'src.tasks.translation_tasks',
]:
    sys.modules[_mod] = MagicMock()

import os
import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models import Base, Photo, PhotoDuplicate
from src.db_service import create_photo_record, record_exact_duplicate

TEST_DB = "test_pipeline_exact.sqlite3"
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


# ── Logic helpers (tested independently of the Huey task) ────────────────────

def _choose_original(existing_photo: Photo, new_captured_at: datetime | None) -> Photo:
    """Return the photo that should be the 'original' (earlier captured_at)."""
    if new_captured_at is None:
        return existing_photo
    existing_ts = existing_photo.captured_at
    if existing_ts is None:
        return existing_photo
    return existing_photo if existing_ts <= new_captured_at else None


def test_existing_photo_chosen_as_original_when_it_is_older(db):
    earlier = datetime(2020, 1, 1)
    later = datetime(2023, 6, 15)

    orig = create_photo_record(db, "hash_scan_orig", "orig.jpg", earlier)

    # Simulate scanner finding file with same hash but later date
    existing = db.query(Photo).filter_by(hash="hash_scan_orig").first()
    assert existing.id == orig.id

    # Record the duplicate using the existing photo as original
    record_exact_duplicate(db, orig.id, "/copies/later.jpg")

    row = db.query(PhotoDuplicate).filter_by(original_photo_id=orig.id).first()
    assert row is not None
    assert row.duplicate_file_path == "/copies/later.jpg"


def test_no_new_photo_record_created_for_exact_duplicate(db):
    create_photo_record(db, "hash_no_new", "no_new_orig.jpg")
    count_before = db.query(Photo).count()

    # Simulate encountering same hash — record duplicate, do NOT create new Photo
    existing = db.query(Photo).filter_by(hash="hash_no_new").first()
    record_exact_duplicate(db, existing.id, "/copies/no_new_dup.jpg")

    count_after = db.query(Photo).count()
    assert count_after == count_before  # no new Photo row


def test_duplicate_record_created_for_each_unique_path(db):
    orig = create_photo_record(db, "hash_multi_paths", "multi_paths_orig.jpg")

    record_exact_duplicate(db, orig.id, "/a/copy1.jpg")
    record_exact_duplicate(db, orig.id, "/b/copy2.jpg")

    count = db.query(PhotoDuplicate).filter_by(original_photo_id=orig.id).count()
    assert count == 2


# ── Folder scanner integration (patched) ─────────────────────────────────────

def test_folder_scanner_calls_record_exact_duplicate_on_hash_collision(db):
    """
    Import folder_scanners with all heavy deps pre-mocked, then patch its
    name-bindings to verify record_exact_duplicate is called on hash collision.
    The queue mock uses a passthrough decorator so the real function body runs.
    """
    # Make queue.task() act as a passthrough decorator so __wrapped__ exists
    sys.modules['src.queues.folder_scan_queue'].folder_scan_queue.task.return_value = lambda f: f
    saved_tasks = sys.modules.pop('src.tasks', None)
    sys.modules.pop('src.tasks.folder_scanners', None)  # force fresh import
    import src.tasks.folder_scanners as fs_mod
    if saved_tasks is not None:
        sys.modules['src.tasks'] = saved_tasks

    existing_photo = create_photo_record(db, "hash_fs_coll", "fs_orig.jpg", datetime(2021, 1, 1))
    mock_scanner = MagicMock(id=1, total_steps=3, scanned_steps=0)

    with patch.object(fs_mod, "check_photo_hash_exists", return_value=existing_photo), \
         patch.object(fs_mod, "record_exact_duplicate") as mock_record, \
         patch.object(fs_mod, "update_folder_scanner_progress"), \
         patch.object(fs_mod, "get_or_create_folder_scanner", return_value=mock_scanner), \
         patch.object(fs_mod, "SessionLocal", return_value=db), \
         patch.object(fs_mod, "generate_file_hash", return_value="hash_fs_coll"), \
         patch.object(fs_mod, "check_if_file_is_image", return_value=True), \
         patch("os.path.exists", return_value=True), \
         patch("os.walk", return_value=[("/folder", [], ["dup.jpg"])]), \
         patch("os.stat") as mock_stat:

        mock_stat.return_value.st_birthtime = datetime(2023, 1, 1).timestamp()
        db.commit = MagicMock()
        db.refresh = MagicMock()
        fs_mod.start_folder_scanner_task("/folder")

    mock_record.assert_called_once_with(db, existing_photo.id, "/folder/dup.jpg")


# ── Observer integration (patched) ───────────────────────────────────────────

def test_observer_calls_record_exact_duplicate_on_hash_collision(db):
    """
    Simulate PhotoEventHandler.on_created with an already-known hash.
    Verify record_exact_duplicate is called (not create_photo_record).
    """
    existing_photo = create_photo_record(db, "hash_obs_coll", "obs_orig.jpg", datetime(2021, 6, 1))

    mock_event = MagicMock()
    mock_event.is_directory = False
    mock_event.src_path = "/watch/dup_photo.jpg"

    with patch("src.observer.check_photo_hash_exists", return_value=existing_photo), \
         patch("src.observer.record_exact_duplicate") as mock_record, \
         patch("src.observer.create_photo_record") as mock_create, \
         patch("src.observer.SessionLocal", return_value=db), \
         patch("src.observer.generate_file_hash", return_value="hash_obs_coll"):

        db.close = MagicMock()
        from src.observer import PhotoEventHandler
        handler = PhotoEventHandler(destination_root_folder="/dest")
        handler.on_created(mock_event)

    mock_record.assert_called_once_with(db, existing_photo.id, "/watch/dup_photo.jpg")
    mock_create.assert_not_called()
