# backend/tests/test_tool_quality.py
import sys
from unittest.mock import MagicMock, patch

import sqlalchemy.types

mock_pgvector = MagicMock()
mock_pgvector.sqlalchemy.Vector = lambda size: sqlalchemy.types.JSON()
sys.modules.setdefault("pgvector", mock_pgvector)
sys.modules.setdefault("pgvector.sqlalchemy", mock_pgvector.sqlalchemy)

for _mod in [
    "sqlite_vec",
    "langgraph",
    "langgraph.graph",
    "src.database",
    "src.vector_db_services",
    "src.ai",
    "src.ai.registry",
    "src.ai.prompts",
    "src.ai.translator",
    "src.queues",
    "src.queues.folder_scan_queue",
    "src.queues.clip_queue",
    "src.queues.vision_queue",
    "src.queues.embedding_queue",
    "src.queues.translation_queue",
    "src.queues.queue_config",
    "src.tasks",
    "src.tasks.utils",
    "src.tasks.folder_scanners",
    "src.tasks.vision_tasks",
    "src.tasks.embedding_tasks",
    "src.tasks.clip_tasks",
    "src.tasks.translation_tasks",
    "src.model_services",
    "src.deps",
    # heavy optional deps not installed in test env
    "exifread",
]:
    sys.modules.setdefault(_mod, MagicMock())


import numpy as np
import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models import Base
from src.models import Photo as PhotoModel


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
    """Create a real minimal JPEG on disk and a DB record."""
    f = tmp_path / filename
    img = Image.new("RGB", (100, 100), color=(128, 128, 128))
    img.save(str(f), "JPEG")
    photo = PhotoModel(hash=filename, file_path=str(f))
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return photo


# ---------------------------------------------------------------------------
# estimate_photo_quality_quick
# ---------------------------------------------------------------------------


def test_estimate_quality_quick_returns_metrics(tmp_path, db, db_factory):
    from src.graphs.tools import estimate_photo_quality_quick

    photo = _make_photo(db, tmp_path)

    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory):
        result = estimate_photo_quality_quick.invoke({"photo_id": photo.id})

    assert "brightness" in result
    assert "blur_variance" in result
    assert "Verdict" in result


def test_estimate_quality_quick_returns_not_found_for_missing_id(db_factory):
    from src.graphs.tools import estimate_photo_quality_quick

    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory):
        result = estimate_photo_quality_quick.invoke({"photo_id": 9999})
    assert "not found" in result.lower()


def test_estimate_quality_quick_verdict_is_one_of_known_values(tmp_path, db, db_factory):
    from src.graphs.tools import estimate_photo_quality_quick

    photo = _make_photo(db, tmp_path)
    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory):
        result = estimate_photo_quality_quick.invoke({"photo_id": photo.id})
    assert any(v in result for v in ("likely garbage", "acceptable", "good"))


def test_estimate_quality_quick_flags_tiny_image(tmp_path, db, db_factory):
    from src.graphs.tools import estimate_photo_quality_quick

    f = tmp_path / "tiny.jpg"
    img = Image.new("RGB", (10, 10), color=(128, 128, 128))
    img.save(str(f), "JPEG")
    photo = PhotoModel(hash="tiny", file_path=str(f))
    db.add(photo)
    db.commit()
    db.refresh(photo)
    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory):
        result = estimate_photo_quality_quick.invoke({"photo_id": photo.id})
    assert "thumbnail" in result.lower() or "tiny" in result.lower()


# ---------------------------------------------------------------------------
# estimate_photo_quality_deep
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_estimate_quality_deep_returns_probe_scores(tmp_path, db, db_factory):
    from unittest.mock import AsyncMock

    from src.graphs.tools import estimate_photo_quality_deep

    photo = _make_photo(db, tmp_path, "deep.jpg")
    vec = np.ones(512).tolist()

    with (
        patch("src.graphs.tools.SessionLocal", side_effect=db_factory),
        patch("src.graphs.tools.call_clip_model", new_callable=AsyncMock, return_value=vec),
    ):
        result = await estimate_photo_quality_deep.ainvoke({"photo_id": photo.id})

    assert "a blurry photo" in result
    assert "Verdict" in result


@pytest.mark.asyncio
async def test_estimate_quality_deep_not_found(db_factory):
    from unittest.mock import AsyncMock

    from src.graphs.tools import estimate_photo_quality_deep

    with (
        patch("src.graphs.tools.SessionLocal", side_effect=db_factory),
        patch("src.graphs.tools.call_clip_model", new_callable=AsyncMock, return_value=np.ones(512).tolist()),
    ):
        result = await estimate_photo_quality_deep.ainvoke({"photo_id": 9999})
    assert "not found" in result.lower()


@pytest.mark.asyncio
async def test_estimate_quality_deep_verdict_present(tmp_path, db, db_factory):
    from unittest.mock import AsyncMock

    from src.graphs.tools import estimate_photo_quality_deep

    photo = _make_photo(db, tmp_path, "deep2.jpg")
    vec = np.ones(512).tolist()
    with (
        patch("src.graphs.tools.SessionLocal", side_effect=db_factory),
        patch("src.graphs.tools.call_clip_model", new_callable=AsyncMock, return_value=vec),
    ):
        result = await estimate_photo_quality_deep.ainvoke({"photo_id": photo.id})
    assert any(v in result for v in ("likely garbage", "good quality"))


# ---------------------------------------------------------------------------
# get_photo_visual_metrics
# ---------------------------------------------------------------------------


def test_get_photo_visual_metrics_returns_all_keys(tmp_path, db, db_factory):
    from src.graphs.tools import get_photo_visual_metrics

    photo = _make_photo(db, tmp_path, "metrics.jpg")
    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory):
        result = get_photo_visual_metrics.invoke({"photo_id": photo.id})
    for key in ("brightness", "blur_variance", "edge_density", "entropy", "colorfulness", "width", "height"):
        assert key in result


def test_get_photo_visual_metrics_not_found(db_factory):
    from src.graphs.tools import get_photo_visual_metrics

    with patch("src.graphs.tools.SessionLocal", side_effect=db_factory):
        result = get_photo_visual_metrics.invoke({"photo_id": 9999})
    assert "not found" in result.lower()


def test_get_visual_metrics_function_returns_dict(tmp_path):
    from src.quality_checks import get_visual_metrics

    f = tmp_path / "test.jpg"
    Image.new("RGB", (200, 150), color=(100, 150, 200)).save(str(f), "JPEG")
    metrics = get_visual_metrics(str(f))
    assert metrics["width"] == 200
    assert metrics["height"] == 150
    assert "brightness" in metrics
    assert "colorfulness" in metrics
    assert metrics["resolution_mpx"] == pytest.approx(0.03, abs=0.01)
