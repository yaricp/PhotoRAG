# backend/tests/test_tool_duplicate.py
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

# imagehash is not installed in the test environment — provide a stub that
# returns valid 16-char hex strings so _hamming_distance can parse them.
class _FakeHash:
    def __init__(self, val="0" * 16): self._v = val
    def __str__(self): return self._v

_mock_imagehash = MagicMock()
_mock_imagehash.dhash.return_value = _FakeHash("0" * 16)
_mock_imagehash.average_hash.return_value = _FakeHash("0" * 16)
_mock_imagehash.phash.return_value = _FakeHash("0" * 16)
sys.modules['imagehash'] = _mock_imagehash

import pytest
import numpy as np
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models import Base, Photo as PhotoModel, PhotoHash


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


def _make_photo(db, tmp_path, filename, color=(128, 128, 128)):
    f = tmp_path / filename
    Image.new("RGB", (64, 64), color=color).save(str(f), "JPEG")
    photo = PhotoModel(hash=filename, file_path=str(f))
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return photo


# ---------------------------------------------------------------------------
# compare_photos_quick
# ---------------------------------------------------------------------------

def test_compare_photos_quick_identical_images_low_distance(tmp_path, db, db_factory):
    from src.graphs.tools import compare_photos_quick
    p1 = _make_photo(db, tmp_path, "q1.jpg", color=(100, 100, 100))
    # Write the same bytes again for p2
    import shutil
    shutil.copy(str(tmp_path / "q1.jpg"), str(tmp_path / "q2.jpg"))
    p2 = PhotoModel(hash="q2.jpg", file_path=str(tmp_path / "q2.jpg"))
    db.add(p2)
    db.commit()
    db.refresh(p2)

    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory):
        result = compare_photos_quick.invoke({"photo_id_a": p1.id, "photo_id_b": p2.id})

    assert "dHash distance" in result
    assert "0" in result  # identical → distance 0


def test_compare_photos_quick_different_images_high_distance(tmp_path, db, db_factory):
    from src.graphs.tools import compare_photos_quick
    p1 = _make_photo(db, tmp_path, "diff1.jpg", color=(0, 0, 0))
    p2 = _make_photo(db, tmp_path, "diff2.jpg", color=(255, 255, 255))

    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory):
        result = compare_photos_quick.invoke({"photo_id_a": p1.id, "photo_id_b": p2.id})

    assert "dHash distance" in result
    assert "Verdict" in result


def test_compare_photos_quick_saves_hashes_to_db(tmp_path, db, db_factory):
    from src.graphs.tools import compare_photos_quick
    p1 = _make_photo(db, tmp_path, "h1.jpg")
    p2 = _make_photo(db, tmp_path, "h2.jpg")

    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory):
        compare_photos_quick.invoke({"photo_id_a": p1.id, "photo_id_b": p2.id})

    session = db_factory()
    ph1 = session.query(PhotoHash).filter_by(photo_id=p1.id).first()
    ph2 = session.query(PhotoHash).filter_by(photo_id=p2.id).first()
    assert ph1 is not None and ph1.dhash is not None
    assert ph2 is not None and ph2.dhash is not None


def test_compare_photos_quick_reuses_existing_hashes(tmp_path, db, db_factory):
    from src.graphs.tools import compare_photos_quick
    p1 = _make_photo(db, tmp_path, "ex1.jpg")
    p2 = _make_photo(db, tmp_path, "ex2.jpg")
    # Pre-seed hashes
    db.add(PhotoHash(photo_id=p1.id, dhash="0" * 16, ahash="0" * 16, phash="0" * 16))
    db.add(PhotoHash(photo_id=p2.id, dhash="f" * 16, ahash="f" * 16, phash="f" * 16))
    db.commit()

    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory):
        result = compare_photos_quick.invoke({"photo_id_a": p1.id, "photo_id_b": p2.id})

    assert "dHash distance" in result


def test_compare_photos_quick_not_found(tmp_path, db, db_factory):
    from src.graphs.tools import compare_photos_quick
    p1 = _make_photo(db, tmp_path, "found.jpg")
    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory):
        result = compare_photos_quick.invoke({"photo_id_a": p1.id, "photo_id_b": 9999})
    assert "not found" in result.lower()


# ---------------------------------------------------------------------------
# compare_photos_deep
# ---------------------------------------------------------------------------

def _make_mock_registry():
    mock_reg = MagicMock()
    call_count = [0]
    def _encode(img):
        call_count[0] += 1
        vec = np.ones(512) * (0.9 if call_count[0] == 1 else 0.9)
        return vec.tolist()
    mock_reg.clip_tagger.model.encode_image.side_effect = _encode
    return mock_reg


def test_compare_photos_deep_returns_similarity(tmp_path, db, db_factory):
    from src.graphs.tools import compare_photos_deep
    p1 = _make_photo(db, tmp_path, "d1.jpg")
    p2 = _make_photo(db, tmp_path, "d2.jpg")
    mock_reg = _make_mock_registry()

    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory), \
         patch("src.graphs.tools.registry", mock_reg):
        result = compare_photos_deep.invoke({"photo_id_a": p1.id, "photo_id_b": p2.id})

    assert "Cosine similarity" in result
    assert "Verdict" in result


def test_compare_photos_deep_not_found(db_factory):
    from src.graphs.tools import compare_photos_deep
    mock_reg = _make_mock_registry()
    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory), \
         patch("src.graphs.tools.registry", mock_reg):
        result = compare_photos_deep.invoke({"photo_id_a": 9999, "photo_id_b": 9998})
    assert "not found" in result.lower()
