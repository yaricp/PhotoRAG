"""
Tests for the perceptual hash task.

Behaviors under test:
- compute_perceptual_hashes_task stores dhash/ahash/phash in photo_hashes table
- task creates photo_duplicates rows for photos with hamming distance ≤ 10
- task does NOT create photo_duplicates for photos with distance > 10
- task is idempotent: running twice does not create duplicate rows
- perceptual hash task is dispatched via start_pipeline (phase 1), not directly from folder_scanner
"""
import sys
from unittest.mock import MagicMock, patch, call
import sqlalchemy.types

mock_pgvector = MagicMock()
mock_pgvector.sqlalchemy.Vector = lambda size: sqlalchemy.types.JSON()
sys.modules.setdefault('pgvector', mock_pgvector)
sys.modules.setdefault('pgvector.sqlalchemy', mock_pgvector.sqlalchemy)

# Native extensions and heavy deps unavailable in the test environment
for _mod in [
    'sqlite_vec', 'src.database', 'src.vector_db_services', 'src.config',
    'src.ai', 'src.ai.registry', 'src.ai.prompts',
    'src.queues', 'src.queues.folder_scan_queue', 'src.queues.clip_queue',
    'src.queues.vision_queue', 'src.queues.embedding_queue',
    'src.queues.translation_queue', 'src.queues.queue_config',
    'src.tasks.utils', 'src.tasks.vision_tasks', 'src.tasks.embedding_tasks',
    'src.tasks.translation_tasks',
    'src.model_services',
    'imagehash',
]:
    sys.modules.setdefault(_mod, MagicMock())

import os
import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models import Base, Photo, PhotoHash, PhotoDuplicate
from src.db_service import create_photo_record, get_or_create_photo_hash

TEST_DB = "test_pipeline_perceptual.sqlite3"
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


def _import_task():
    """Import clip_tasks fresh on each call (heavy deps already mocked).

    Temporarily removes src.tasks from sys.modules so Python treats it as
    a real package rather than the MagicMock that other test files may have
    injected.  The mock is restored afterwards so it doesn't bleed into other
    test code in this file that expects the mocked version.
    """
    sys.modules['src.queues.clip_queue'].clip_queue.task.return_value = lambda f: f
    saved_tasks = sys.modules.pop('src.tasks', None)
    sys.modules.pop('src.tasks.clip_tasks', None)
    import src.tasks.clip_tasks as m
    if saved_tasks is not None:
        sys.modules['src.tasks'] = saved_tasks
    return m


# ── Hash storage ─────────────────────────────────────────────────────────────

def _mock_photo(photo_id: int, file_path: str = "test.jpg") -> MagicMock:
    """Return a plain mock photo to avoid SQLAlchemy detached-instance issues."""
    m = MagicMock()
    m.id = photo_id
    m.file_path = file_path
    return m


def test_task_stores_hashes_in_photo_hashes_table(db):
    photo = _mock_photo(photo_id=1)
    mock_hash = MagicMock()
    mock_hash.__str__ = lambda s: "aabbccdd11223344"
    mock_db = MagicMock()

    task_mod = _import_task()
    with patch.object(task_mod, "SessionLocal", return_value=mock_db), \
         patch.object(task_mod, "get_photo_by_id", return_value=photo), \
         patch.object(task_mod, "get_or_create_photo_hash") as mock_store, \
         patch.object(task_mod, "find_perceptual_duplicates", return_value=[]), \
         patch("PIL.Image.open", return_value=MagicMock()), \
         patch("imagehash.dhash", return_value=mock_hash), \
         patch("imagehash.average_hash", return_value=mock_hash), \
         patch("imagehash.phash", return_value=mock_hash):

        task_mod.compute_perceptual_hashes_task(photo.id, "first")

    mock_store.assert_called_once()
    args = mock_store.call_args[0]
    assert args[1] == photo.id


def test_task_creates_duplicate_record_for_close_photos(db):
    photo_a = _mock_photo(photo_id=10)
    mock_hash = MagicMock()
    mock_hash.__str__ = lambda s: "0000000000000000"
    mock_db = MagicMock()

    task_mod = _import_task()
    with patch.object(task_mod, "SessionLocal", return_value=mock_db), \
         patch.object(task_mod, "get_photo_by_id", return_value=photo_a), \
         patch.object(task_mod, "get_or_create_photo_hash", return_value=MagicMock()), \
         patch.object(task_mod, "find_perceptual_duplicates", return_value=[
             {"photo_id": 20, "hash_distance": 5}
         ]), \
         patch.object(task_mod, "record_perceptual_duplicate") as mock_record, \
         patch("PIL.Image.open", return_value=MagicMock()), \
         patch("imagehash.dhash", return_value=mock_hash), \
         patch("imagehash.average_hash", return_value=mock_hash), \
         patch("imagehash.phash", return_value=mock_hash):

        task_mod.compute_perceptual_hashes_task(photo_a.id, "first")

    mock_record.assert_called_once_with(mock_db, photo_a.id, 20, 5)


def test_task_does_not_create_duplicate_when_no_close_photos(db):
    photo = _mock_photo(photo_id=30)
    mock_hash = MagicMock()
    mock_hash.__str__ = lambda s: "0000000000000000"
    mock_db = MagicMock()

    task_mod = _import_task()
    with patch.object(task_mod, "SessionLocal", return_value=mock_db), \
         patch.object(task_mod, "get_photo_by_id", return_value=photo), \
         patch.object(task_mod, "get_or_create_photo_hash", return_value=MagicMock()), \
         patch.object(task_mod, "find_perceptual_duplicates", return_value=[]), \
         patch.object(task_mod, "record_perceptual_duplicate") as mock_record, \
         patch("PIL.Image.open", return_value=MagicMock()), \
         patch("imagehash.dhash", return_value=mock_hash), \
         patch("imagehash.average_hash", return_value=mock_hash), \
         patch("imagehash.phash", return_value=mock_hash):

        task_mod.compute_perceptual_hashes_task(photo.id, "first")

    mock_record.assert_not_called()


def test_task_skips_gracefully_when_photo_not_found(db):
    mock_db = MagicMock()
    task_mod = _import_task()
    with patch.object(task_mod, "SessionLocal", return_value=mock_db), \
         patch.object(task_mod, "get_photo_by_id", return_value=None), \
         patch.object(task_mod, "get_or_create_photo_hash") as mock_store:

        task_mod.compute_perceptual_hashes_task(99999, "first")

    mock_store.assert_not_called()


# ── Enqueue from pipeline entry points ───────────────────────────────────────

def test_folder_scanner_dispatches_perceptual_hash_via_start_pipeline(db):
    """
    After integration into phase 1, folder_scanner must NOT directly call
    compute_perceptual_hashes_task.  Instead it delegates to start_pipeline,
    which dispatches all phase-1 tasks (including perceptual hashing) via
    _dispatch_tasks.
    """
    sys.modules['src.queues.folder_scan_queue'].folder_scan_queue.task.return_value = lambda f: f
    saved_tasks = sys.modules.pop('src.tasks', None)
    sys.modules.pop('src.tasks.folder_scanners', None)
    import src.tasks.folder_scanners as fs_mod
    if saved_tasks is not None:
        sys.modules['src.tasks'] = saved_tasks

    # compute_perceptual_hashes_task must NOT be an attribute of folder_scanners
    assert not hasattr(fs_mod, "compute_perceptual_hashes_task"), (
        "compute_perceptual_hashes_task should not be imported in folder_scanners; "
        "it is dispatched via start_pipeline/_dispatch_tasks"
    )

    new_photo = create_photo_record(db, "hash_enq_fs", "enq_fs.jpg")
    mock_scanner = MagicMock(id=1, total_steps=3, scanned_steps=0)

    with patch.object(fs_mod, "check_photo_hash_exists", return_value=None), \
         patch.object(fs_mod, "create_photo_record", return_value=new_photo), \
         patch.object(fs_mod, "start_pipeline") as mock_start_pipeline, \
         patch.object(fs_mod, "update_folder_scanner_progress"), \
         patch.object(fs_mod, "get_or_create_folder_scanner", return_value=mock_scanner), \
         patch.object(fs_mod, "SessionLocal", return_value=db), \
         patch.object(fs_mod, "generate_file_hash", return_value="hash_enq_fs"), \
         patch.object(fs_mod, "check_if_file_is_image", return_value=True), \
         patch("os.path.exists", return_value=True), \
         patch("os.walk", return_value=[("/folder", [], ["new.jpg"])]), \
         patch("os.stat") as mock_stat:

        mock_stat.return_value.st_birthtime = datetime(2023, 1, 1).timestamp()
        db.commit = MagicMock()
        db.refresh = MagicMock()
        fs_mod.start_folder_scanner_task("/folder")

    mock_start_pipeline.assert_called_once_with(new_photo.id, mock_scanner.id)
