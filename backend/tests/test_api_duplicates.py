"""
Tests for the GET /api/duplicates/ endpoint and extended DELETE /api/photos/{id}.

Behaviors under test:
- GET /api/duplicates/ returns {"exact": [...], "perceptual": [...]} structure
- GET /api/duplicates/ returns 200 with empty lists when no duplicates exist
- DELETE /api/photos/{id} removes the file from disk (os.remove called)
- DELETE /api/photos/{id} returns 404 when photo does not exist
"""
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
]:
    sys.modules[_mod] = MagicMock()

import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models import Base, Photo, PhotoDuplicate

TEST_DB = "test_api_duplicates.sqlite3"
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


@pytest.fixture
def client(db):
    # Import app fresh (all heavy deps already mocked at module level)
    sys.modules.pop('src.main', None)
    import src.main as main_mod
    # Override the get_db dependency to use our test session
    def override_get_db():
        yield db
    main_mod.app.dependency_overrides[sys.modules['src.deps'].get_db] = override_get_db
    return TestClient(main_mod.app)


# ── GET /api/duplicates/ ──────────────────────────────────────────────────────

def test_get_duplicates_returns_200_with_empty_lists(client):
    response = client.get("/api/duplicates/")
    assert response.status_code == 200
    data = response.json()
    assert "exact" in data
    assert "perceptual" in data
    assert isinstance(data["exact"], list)
    assert isinstance(data["perceptual"], list)


def test_get_duplicates_returns_exact_group(client, db):
    orig = Photo(hash="api_orig", file_path="/photos/orig.jpg")
    db.add(orig)
    db.flush()
    db.add(PhotoDuplicate(
        original_photo_id=orig.id,
        duplicate_file_path="/photos/dup.jpg",
        match_type="exact",
    ))
    db.commit()

    response = client.get("/api/duplicates/")
    assert response.status_code == 200
    data = response.json()
    assert len(data["exact"]) >= 1
    group = next(g for g in data["exact"] if g["original"]["id"] == orig.id)
    assert group["duplicates"][0]["file_path"] == "/photos/dup.jpg"


def test_get_duplicates_returns_perceptual_group(client, db):
    orig = Photo(hash="api_perc_orig", file_path="/photos/perc_orig.jpg")
    dup = Photo(hash="api_perc_dup", file_path="/photos/perc_dup.jpg")
    db.add_all([orig, dup])
    db.flush()
    db.add(PhotoDuplicate(
        original_photo_id=orig.id,
        duplicate_photo_id=dup.id,
        match_type="perceptual",
        hash_distance=6,
    ))
    db.commit()

    response = client.get("/api/duplicates/")
    assert response.status_code == 200
    data = response.json()
    assert len(data["perceptual"]) >= 1
    group = next(g for g in data["perceptual"] if g["original"]["id"] == orig.id)
    assert group["duplicates"][0]["hash_distance"] == 6


# ── DELETE /api/photos/{id} ───────────────────────────────────────────────────

def test_delete_photo_calls_os_remove(client, db):
    photo = Photo(hash="api_del", file_path="/photos/to_delete.jpg")
    db.add(photo)
    db.commit()
    db.refresh(photo)
    photo_id = photo.id

    with patch("os.path.exists", return_value=True), \
         patch("os.remove") as mock_remove:
        response = client.delete(f"/api/photos/{photo_id}")

    assert response.status_code == 200
    mock_remove.assert_called_once_with("/photos/to_delete.jpg")


def test_delete_photo_returns_404_when_not_found(client):
    response = client.delete("/api/photos/99999")
    assert response.status_code == 404
