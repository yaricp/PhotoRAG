# Garbage / Bad Photo Detection — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect technically-poor photos (thumbnail, no-EXIF, brightness, edge density, blur, entropy, screenshot) during ingestion, persist flags in a dedicated table, expose them via API, and surface them in a new GarbageBadPhotoPage with archive/delete actions per card.

**Architecture:** Seven pure detection functions in `quality_checks.py` are called from Huey tasks embedded in the existing pipeline (phase 1 for 6 checks, phase 3 for screenshot). Results land in a new `photo_quality_issues` table. Two new FastAPI endpoints feed a new frontend page with four expandable sections (technical fully implemented, three others as placeholders).

**Tech Stack:** Python 3.13 · SQLAlchemy · Huey · Pillow 12 · NumPy 2 · FastAPI · React 18 · TypeScript · Vitest · MSW

---

## File Map

**Create:**
- `backend/src/quality_checks.py` — 7 pure detection functions (no side effects, no DB)
- `backend/src/tasks/quality_tasks.py` — 5 Huey tasks (brightness, edge_density, blur, entropy, screenshot)
- `backend/tests/test_quality_checks.py` — unit tests for detection functions
- `backend/tests/test_quality_tasks.py` — Huey task integration tests
- `backend/tests/test_api_garbage.py` — FastAPI garbage endpoint tests
- `backend/tests/test_models_quality.py` — ORM model + cascade tests
- `frontend/src/pages/GarbageBadPhotoPage.tsx`
- `frontend/src/pages/GarbageBadPhotoPage.css`
- `frontend/src/pages/__tests__/GarbageBadPhotoPage.test.tsx`

**Modify:**
- `backend/src/models.py` — add `PhotoQualityIssue` model, add relationship to `Photo`
- `backend/src/db_service.py` — add `create_quality_issue`, `get_quality_summary`, `get_photos_by_issue_type`
- `backend/src/tasks/clip_tasks.py` — extend `metadata_task` with resolution + EXIF checks
- `backend/src/tasks/utils.py` — update `phase_logic` + `_dispatch_tasks`
- `backend/src/main.py` — add 2 garbage endpoints, import new DB functions
- `frontend/src/api/client.ts` — add `getGarbageSummary`, `getGarbagePhotos`, `GarbageSummary`
- `frontend/src/components/photos/PhotoCard.tsx` — add optional `onArchive`/`onDelete` props
- `frontend/src/components/photos/PhotoCard.css` — add action button styles
- `frontend/src/pages/AppRoutes.tsx` — add `/garbage` route
- `frontend/src/components/ui/Sidebar.tsx` — add garbage nav link

---

## Task 1: PhotoQualityIssue ORM Model

**Files:**
- Modify: `backend/src/models.py`
- Create: `backend/tests/test_models_quality.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_models_quality.py
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
from src.models import Base, Photo, PhotoQualityIssue

TEST_DB = "test_models_quality.sqlite3"
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


def _make_photo(db) -> Photo:
    p = Photo(hash="abc123", file_path="/tmp/test.jpg")
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def test_create_quality_issue(db):
    photo = _make_photo(db)
    issue = PhotoQualityIssue(photo_id=photo.id, issue_type="blur", score=42.5)
    db.add(issue)
    db.commit()
    db.refresh(issue)
    assert issue.id is not None
    assert issue.issue_type == "blur"
    assert issue.score == 42.5
    assert issue.detected_at is not None


def test_photo_can_have_multiple_issues(db):
    photo = _make_photo(db)
    for itype in ("blur", "no_exif", "thumbnail"):
        db.add(PhotoQualityIssue(photo_id=photo.id, issue_type=itype, score=0.0))
    db.commit()
    assert len(photo.quality_issues) == 3


def test_cascade_delete_removes_issues(db):
    photo = _make_photo(db)
    db.add(PhotoQualityIssue(photo_id=photo.id, issue_type="blur", score=1.0))
    db.commit()
    photo_id = photo.id
    db.delete(photo)
    db.commit()
    remaining = db.query(PhotoQualityIssue).filter_by(photo_id=photo_id).all()
    assert remaining == []
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd backend
python -m pytest tests/test_models_quality.py -v
```
Expected: `ImportError: cannot import name 'PhotoQualityIssue' from 'src.models'`

- [ ] **Step 3: Add PhotoQualityIssue to models.py**

In `backend/src/models.py`, after the `PhotoDuplicate` class, add:

```python
class PhotoQualityIssue(Base):
    __tablename__ = "photo_quality_issues"

    id = Column(Integer, primary_key=True)
    photo_id = Column(Integer, ForeignKey("photos.id", ondelete="CASCADE"), nullable=False, index=True)
    issue_type = Column(String, nullable=False)
    score = Column(Float, nullable=True)
    detected_at = Column(DateTime, default=datetime.utcnow)

    photo = relationship("Photo", back_populates="quality_issues")
```

Then in the `Photo` class (after the `duplicates_as_duplicate` relationship), add:

```python
    quality_issues = relationship("PhotoQualityIssue", back_populates="photo", cascade="all, delete-orphan")
```

- [ ] **Step 4: Run to verify it passes**

```bash
cd backend
python -m pytest tests/test_models_quality.py -v
```
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/src/models.py backend/tests/test_models_quality.py
git commit -m "feat: add PhotoQualityIssue ORM model with cascade delete"
```

---

## Task 2: DB Service Functions for Quality Issues

**Files:**
- Modify: `backend/src/db_service.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_models_quality.py` (imports already present):

```python
from src.db_service import create_quality_issue, get_quality_summary, get_photos_by_issue_type


def test_create_quality_issue_service(db):
    photo = _make_photo(db)
    issue = create_quality_issue(db, photo_id=photo.id, issue_type="brightness", score=15.3)
    db.commit()
    assert issue.id is not None
    assert issue.photo_id == photo.id


def test_get_quality_summary_counts(db):
    p1 = _make_photo(db)
    p2 = _make_photo(db)
    create_quality_issue(db, p1.id, "blur", 50.0)
    create_quality_issue(db, p2.id, "blur", 30.0)
    create_quality_issue(db, p1.id, "no_exif", 0.0)
    db.commit()
    summary = get_quality_summary(db)
    assert summary["blur"] == 2
    assert summary["no_exif"] == 1


def test_get_photos_by_issue_type(db):
    p1 = _make_photo(db)
    p2 = _make_photo(db)
    create_quality_issue(db, p1.id, "thumbnail", 900.0)
    create_quality_issue(db, p2.id, "thumbnail", 400.0)
    db.commit()
    photos, total = get_photos_by_issue_type(db, "thumbnail")
    assert total == 2
    ids = {p.id for p in photos}
    assert p1.id in ids and p2.id in ids


def test_get_photos_by_issue_type_pagination(db):
    for _ in range(5):
        p = _make_photo(db)
        create_quality_issue(db, p.id, "entropy", 1.0)
    db.commit()
    photos, total = get_photos_by_issue_type(db, "entropy", skip=0, limit=3)
    assert total == 5
    assert len(photos) == 3
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd backend
python -m pytest tests/test_models_quality.py -v -k "service or summary or issue_type"
```
Expected: `ImportError: cannot import name 'create_quality_issue' from 'src.db_service'`

- [ ] **Step 3: Add functions to db_service.py**

At the top of `backend/src/db_service.py`, add `PhotoQualityIssue` to the models import:

```python
from src.models import (
    Photo, Tag, Person, Keyword, Category, PhotoTag, PhotoCategory, Camera, Geoposition,
    ModelState, Watcher, ProcessingJob, FolderScanner, AIModelConfig,
    PhotoEmbedding, PhotoHash, PhotoDuplicate, PhotoQualityIssue,
)
```

At the end of `backend/src/db_service.py`, add:

```python
# ── Quality issue helpers ──────────────────────────────────────────────────

def create_quality_issue(
    db: Session, photo_id: int, issue_type: str, score: float | None
) -> PhotoQualityIssue:
    issue = PhotoQualityIssue(photo_id=photo_id, issue_type=issue_type, score=score)
    db.add(issue)
    return issue


def get_quality_summary(db: Session) -> dict[str, int]:
    """Return count of distinct photos flagged per issue_type."""
    from sqlalchemy import func
    rows = (
        db.query(PhotoQualityIssue.issue_type, func.count(PhotoQualityIssue.photo_id.distinct()))
        .group_by(PhotoQualityIssue.issue_type)
        .all()
    )
    return {issue_type: count for issue_type, count in rows}


def get_photos_by_issue_type(
    db: Session, issue_type: str, skip: int = 0, limit: int = 20
) -> tuple[list[Photo], int]:
    """Return paginated photos that have been flagged with the given issue_type."""
    query = (
        db.query(Photo)
        .join(PhotoQualityIssue, Photo.id == PhotoQualityIssue.photo_id)
        .filter(PhotoQualityIssue.issue_type == issue_type)
        .distinct()
    )
    total = query.count()
    photos = query.offset(skip).limit(limit).all()
    return photos, total
```

- [ ] **Step 4: Run to verify it passes**

```bash
cd backend
python -m pytest tests/test_models_quality.py -v
```
Expected: all tests PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/src/db_service.py backend/tests/test_models_quality.py
git commit -m "feat: add quality issue DB service functions"
```

---

## Task 3: Pure Detection Functions (quality_checks.py)

**Files:**
- Create: `backend/src/quality_checks.py`
- Create: `backend/tests/test_quality_checks.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_quality_checks.py
"""
Unit tests for quality_checks.py.
Each test creates a synthetic PIL image in memory — no real files needed.
"""
import io
import numpy as np
import pytest
from PIL import Image, ImageDraw

from src.quality_checks import (
    check_resolution,
    check_exif,
    check_brightness,
    check_edge_density,
    check_blur,
    check_entropy,
    check_screenshot,
)


def _save_tmp(img: Image.Image, tmp_path, name: str) -> str:
    path = str(tmp_path / name)
    img.save(path, format="JPEG")
    return path


# ── check_resolution ──────────────────────────────────────────────────────

def test_check_resolution_small_is_thumbnail(tmp_path):
    img = Image.new("RGB", (50, 50), color=(128, 128, 128))
    path = _save_tmp(img, tmp_path, "small.jpg")
    is_thumb, pixels = check_resolution(path)
    assert is_thumb is True
    assert pixels == 2500.0


def test_check_resolution_normal_not_thumbnail(tmp_path):
    img = Image.new("RGB", (800, 600), color=(128, 128, 128))
    path = _save_tmp(img, tmp_path, "normal.jpg")
    is_thumb, pixels = check_resolution(path)
    assert is_thumb is False
    assert pixels == 480_000.0


# ── check_exif ────────────────────────────────────────────────────────────

def test_check_exif_empty_dict_flagged():
    flagged, score = check_exif({})
    assert flagged is True
    assert score == 0.0


def test_check_exif_with_make_not_flagged():
    flagged, _ = check_exif({"Make": "Apple", "Model": "iPhone 14"})
    assert flagged is False


def test_check_exif_with_date_not_flagged():
    flagged, _ = check_exif({"DateTimeOriginal": "2023:01:01 12:00:00"})
    assert flagged is False


def test_check_exif_only_unrelated_keys_flagged():
    flagged, _ = check_exif({"Software": "Photoshop", "XResolution": 72})
    assert flagged is True


# ── check_brightness ──────────────────────────────────────────────────────

def test_check_brightness_dark_flagged(tmp_path):
    img = Image.new("RGB", (100, 100), color=(5, 5, 5))
    path = _save_tmp(img, tmp_path, "dark.jpg")
    flagged, mean = check_brightness(path)
    assert flagged is True
    assert mean < 30


def test_check_brightness_normal_not_flagged(tmp_path):
    img = Image.new("RGB", (100, 100), color=(128, 128, 128))
    path = _save_tmp(img, tmp_path, "normal.jpg")
    flagged, mean = check_brightness(path)
    assert flagged is False
    assert 30 <= mean <= 220


def test_check_brightness_overexposed_flagged(tmp_path):
    img = Image.new("RGB", (100, 100), color=(250, 250, 250))
    path = _save_tmp(img, tmp_path, "bright.jpg")
    flagged, mean = check_brightness(path)
    assert flagged is True
    assert mean > 220


# ── check_edge_density ────────────────────────────────────────────────────

def test_check_edge_density_flat_image_flagged(tmp_path):
    img = Image.new("RGB", (200, 200), color=(100, 100, 100))
    path = _save_tmp(img, tmp_path, "flat.jpg")
    flagged, ratio = check_edge_density(path)
    assert flagged is True
    assert ratio < 0.02


def test_check_edge_density_image_with_edges_not_flagged(tmp_path):
    img = Image.new("RGB", (200, 200), color=(200, 200, 200))
    draw = ImageDraw.Draw(img)
    for i in range(0, 200, 10):
        draw.line([(0, i), (200, i)], fill=(0, 0, 0), width=2)
        draw.line([(i, 0), (i, 200)], fill=(0, 0, 0), width=2)
    path = _save_tmp(img, tmp_path, "edges.jpg")
    flagged, ratio = check_edge_density(path)
    assert flagged is False
    assert ratio >= 0.02


# ── check_blur ────────────────────────────────────────────────────────────

def test_check_blur_uniform_image_is_blurry(tmp_path):
    img = Image.new("L", (100, 100), color=128)
    path = str(tmp_path / "uniform.png")
    img.save(path, format="PNG")
    flagged, variance = check_blur(path)
    assert flagged is True
    assert variance < 100.0


def test_check_blur_sharp_image_not_blurry(tmp_path):
    arr = np.zeros((100, 100), dtype=np.uint8)
    arr[::2, :] = 255  # alternating rows — maximum sharpness
    img = Image.fromarray(arr, mode="L")
    path = str(tmp_path / "sharp.png")
    img.save(path, format="PNG")
    flagged, variance = check_blur(path)
    assert flagged is False
    assert variance >= 100.0


# ── check_entropy ─────────────────────────────────────────────────────────

def test_check_entropy_uniform_image_low(tmp_path):
    img = Image.new("RGB", (100, 100), color=(100, 100, 100))
    path = _save_tmp(img, tmp_path, "uniform.jpg")
    flagged, entropy = check_entropy(path)
    assert flagged is True
    assert entropy < 3.0


def test_check_entropy_noisy_image_high(tmp_path):
    arr = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
    img = Image.fromarray(arr, mode="RGB")
    path = _save_tmp(img, tmp_path, "noisy.jpg")
    flagged, entropy = check_entropy(path)
    assert flagged is False
    assert entropy >= 3.0


# ── check_screenshot ──────────────────────────────────────────────────────

def test_check_screenshot_ui_like_flagged(tmp_path):
    # UI-like: large solid-color blocks — very few distinct colors
    img = Image.new("RGB", (400, 300), color=(240, 240, 240))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, 400, 40], fill=(70, 130, 180))    # title bar
    draw.rectangle([0, 260, 400, 300], fill=(200, 200, 200))  # status bar
    draw.rectangle([10, 50, 150, 80], fill=(100, 100, 200))   # button
    path = _save_tmp(img, tmp_path, "ui.jpg")
    flagged, score = check_screenshot(path)
    assert flagged is True
    assert score > 0.45


def test_check_screenshot_natural_photo_not_flagged(tmp_path):
    arr = np.random.randint(0, 256, (300, 400, 3), dtype=np.uint8)
    img = Image.fromarray(arr, mode="RGB")
    path = _save_tmp(img, tmp_path, "natural.jpg")
    flagged, score = check_screenshot(path)
    assert flagged is False
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd backend
python -m pytest tests/test_quality_checks.py -v
```
Expected: `ModuleNotFoundError: No module named 'src.quality_checks'`

- [ ] **Step 3: Implement quality_checks.py**

```python
# backend/src/quality_checks.py
from PIL import Image, ImageFilter, ImageStat
import numpy as np

THUMBNAIL_MAX_PIXELS = 10_000  # 100×100

_EXIF_CAMERA_KEYS = ("Make", "Model")
_EXIF_DATE_KEYS = ("DateTimeOriginal", "DateTimeDigitized", "DateTime")


def check_resolution(file_path: str) -> tuple[bool, float]:
    """True if actual pixel count < 10 000 (thumbnail-sized)."""
    with Image.open(file_path) as img:
        w, h = img.size
    pixels = float(w * h)
    return pixels < THUMBNAIL_MAX_PIXELS, pixels


def check_exif(exif_raw: dict) -> tuple[bool, float]:
    """True if no camera make/model AND no capture datetime — likely an internet copy."""
    has_camera = any(exif_raw.get(k) for k in _EXIF_CAMERA_KEYS)
    has_date = any(exif_raw.get(k) for k in _EXIF_DATE_KEYS)
    return not (has_camera or has_date), 0.0


def check_brightness(file_path: str) -> tuple[bool, float]:
    """True if mean luminance < 30 (too dark) or > 220 (overexposed)."""
    with Image.open(file_path) as img:
        mean = ImageStat.Stat(img.convert("L")).mean[0]
    return mean < 30.0 or mean > 220.0, round(mean, 2)


def check_edge_density(file_path: str) -> tuple[bool, float]:
    """True if < 2% of pixels are edges — flat/featureless image."""
    with Image.open(file_path) as img:
        arr = np.array(img.convert("L").filter(ImageFilter.FIND_EDGES))
    ratio = float((arr > 10).sum()) / arr.size
    return ratio < 0.02, round(ratio, 4)


def check_blur(file_path: str) -> tuple[bool, float]:
    """True if Laplacian variance < 100 — image is blurry."""
    with Image.open(file_path) as img:
        arr = np.array(img.convert("L"), dtype=np.float64)
    lap = (
        arr[:-2, 1:-1] + arr[2:, 1:-1] +
        arr[1:-1, :-2] + arr[1:-1, 2:] -
        4 * arr[1:-1, 1:-1]
    )
    variance = float(lap.var())
    return variance < 100.0, round(variance, 2)


def check_entropy(file_path: str) -> tuple[bool, float]:
    """True if image entropy < 3.0 bits — low information content."""
    with Image.open(file_path) as img:
        entropy = img.convert("L").entropy()
    return entropy < 3.0, round(entropy, 4)


def check_screenshot(file_path: str) -> tuple[bool, float]:
    """True if > 45% of pixels fall in the top-10 colors of a 64-color quantization.
    Screenshots have large flat-color regions (menus, toolbars, backgrounds)."""
    with Image.open(file_path) as img:
        small = img.convert("RGB").resize((256, 256))
        quantized = small.quantize(colors=64)
    arr = np.array(quantized)
    counts = np.bincount(arr.flatten(), minlength=64)
    top10_sum = sum(sorted(counts.tolist(), reverse=True)[:10])
    score = float(top10_sum) / arr.size
    return score > 0.45, round(score, 4)
```

- [ ] **Step 4: Run to verify all pass**

```bash
cd backend
python -m pytest tests/test_quality_checks.py -v
```
Expected: all tests PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/src/quality_checks.py backend/tests/test_quality_checks.py
git commit -m "feat: add pure quality detection functions with tests"
```

---

## Task 4: Extend metadata_task with Resolution + EXIF Checks

**Files:**
- Modify: `backend/src/tasks/clip_tasks.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_quality_tasks.py`:

```python
# backend/tests/test_quality_tasks.py
"""
Tests for quality detection tasks.
Uses unittest.mock to avoid real Huey queues and DB connections.
"""
import sys
from unittest.mock import MagicMock, patch, call
import sqlalchemy.types

mock_pgvector = MagicMock()
mock_pgvector.sqlalchemy.Vector = lambda size: sqlalchemy.types.JSON()
sys.modules['pgvector'] = mock_pgvector
sys.modules['pgvector.sqlalchemy'] = mock_pgvector.sqlalchemy

import pytest
from PIL import Image


def _make_jpeg(tmp_path, name="test.jpg", size=(800, 600), color=(128, 128, 128)) -> str:
    path = str(tmp_path / name)
    Image.new("RGB", size, color=color).save(path, format="JPEG")
    return path


# ── metadata_task resolution check ────────────────────────────────────────

def test_metadata_task_flags_thumbnail(tmp_path):
    """metadata_task creates a 'thumbnail' quality issue for a very small image."""
    small_path = _make_jpeg(tmp_path, "small.jpg", size=(50, 50))

    mock_photo = MagicMock()
    mock_photo.file_path = small_path
    mock_photo.id = 1

    mock_db = MagicMock()

    with (
        patch("src.tasks.clip_tasks.get_photo_by_id", return_value=mock_photo),
        patch("src.tasks.clip_tasks.extract_exif", return_value={"Make": "Apple"}),
        patch("src.tasks.clip_tasks.GeoEnricher") as mock_geo_cls,
        patch("src.tasks.clip_tasks.get_or_create_camera"),
        patch("src.tasks.clip_tasks.update_photo_geoposition"),
        patch("src.tasks.clip_tasks.create_quality_issue") as mock_create_qi,
        patch("src.tasks.clip_tasks._finish_task"),
        patch("src.tasks.clip_tasks.SessionLocal", return_value=mock_db),
    ):
        mock_geo_cls.return_value.geocode_photo.return_value = {}
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)

        from src.tasks.clip_tasks import metadata_task
        metadata_task.__wrapped__(1, phase="first")

        calls = [c.kwargs.get("issue_type") or c.args[2] for c in mock_create_qi.call_args_list]
        assert "thumbnail" in calls


def test_metadata_task_flags_no_exif(tmp_path):
    """metadata_task creates a 'no_exif' quality issue when EXIF is empty."""
    path = _make_jpeg(tmp_path, "no_exif.jpg", size=(800, 600))

    mock_photo = MagicMock()
    mock_photo.file_path = path
    mock_photo.id = 2

    mock_db = MagicMock()

    with (
        patch("src.tasks.clip_tasks.get_photo_by_id", return_value=mock_photo),
        patch("src.tasks.clip_tasks.extract_exif", return_value={}),
        patch("src.tasks.clip_tasks.GeoEnricher") as mock_geo_cls,
        patch("src.tasks.clip_tasks.create_quality_issue") as mock_create_qi,
        patch("src.tasks.clip_tasks._finish_task"),
        patch("src.tasks.clip_tasks.SessionLocal", return_value=mock_db),
    ):
        mock_geo_cls.return_value.geocode_photo.return_value = {}
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)

        from src.tasks.clip_tasks import metadata_task
        metadata_task.__wrapped__(2, phase="first")

        calls = [c.kwargs.get("issue_type") or c.args[2] for c in mock_create_qi.call_args_list]
        assert "no_exif" in calls
```

- [ ] **Step 2: Run to verify the test fails**

```bash
cd backend
python -m pytest tests/test_quality_tasks.py::test_metadata_task_flags_thumbnail tests/test_quality_tasks.py::test_metadata_task_flags_no_exif -v
```
Expected: FAIL — `create_quality_issue` is not called

- [ ] **Step 3: Update metadata_task in clip_tasks.py**

Add the imports at the top of `backend/src/tasks/clip_tasks.py`:

```python
from src.db_service import (
    get_photo_by_id,
    get_or_create_camera,
    update_photo_geoposition,
    add_photo_tag_with_score,
    get_or_create_category,
    add_photo_category_with_score,
    delete_job,
    get_or_create_photo_hash,
    find_perceptual_duplicates,
    record_perceptual_duplicate,
    create_quality_issue,
)
from src.quality_checks import check_resolution, check_exif
```

Inside `metadata_task`, after `db.commit()` (after the existing geo/camera/exif lines) and before `_finish_task`, add:

```python
        # Quality checks: resolution + EXIF (CPU-only, runs in metadata phase)
        is_thumbnail, px_count = check_resolution(photo.file_path)
        if is_thumbnail:
            create_quality_issue(db, photo.id, "thumbnail", px_count)

        is_no_exif, _ = check_exif(exif_raw)
        if is_no_exif:
            create_quality_issue(db, photo.id, "no_exif", 0.0)

        db.commit()
```

(This second `db.commit()` flushes the quality issues after the existing EXIF commit.)

- [ ] **Step 4: Run to verify the tests pass**

```bash
cd backend
python -m pytest tests/test_quality_tasks.py::test_metadata_task_flags_thumbnail tests/test_quality_tasks.py::test_metadata_task_flags_no_exif -v
```
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/src/tasks/clip_tasks.py backend/tests/test_quality_tasks.py
git commit -m "feat: extend metadata_task to flag thumbnail and no-EXIF photos"
```

---

## Task 5: New Phase-1 Quality Tasks (Brightness, Edge Density, Blur, Entropy)

**Files:**
- Create: `backend/src/tasks/quality_tasks.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_quality_tasks.py`:

```python
def test_brightness_task_flags_dark_image(tmp_path):
    dark_path = _make_jpeg(tmp_path, "dark.jpg", color=(5, 5, 5))
    mock_photo = MagicMock()
    mock_photo.file_path = dark_path
    mock_photo.id = 10
    mock_db = MagicMock()

    with (
        patch("src.tasks.quality_tasks.get_photo_by_id", return_value=mock_photo),
        patch("src.tasks.quality_tasks.create_quality_issue") as mock_cqi,
        patch("src.tasks.quality_tasks._finish_task"),
        patch("src.tasks.quality_tasks.SessionLocal", return_value=mock_db),
    ):
        from src.tasks.quality_tasks import brightness_task
        brightness_task.__wrapped__(10, phase="first")
        assert mock_cqi.called
        issue_type = mock_cqi.call_args[0][2]
        assert issue_type == "brightness"


def test_brightness_task_skips_normal_image(tmp_path):
    normal_path = _make_jpeg(tmp_path, "normal.jpg", color=(128, 128, 128))
    mock_photo = MagicMock()
    mock_photo.file_path = normal_path
    mock_photo.id = 11
    mock_db = MagicMock()

    with (
        patch("src.tasks.quality_tasks.get_photo_by_id", return_value=mock_photo),
        patch("src.tasks.quality_tasks.create_quality_issue") as mock_cqi,
        patch("src.tasks.quality_tasks._finish_task"),
        patch("src.tasks.quality_tasks.SessionLocal", return_value=mock_db),
    ):
        from src.tasks.quality_tasks import brightness_task
        brightness_task.__wrapped__(11, phase="first")
        assert not mock_cqi.called


def test_blur_task_flags_uniform_image(tmp_path):
    flat_path = str(tmp_path / "flat.png")
    Image.new("L", (100, 100), color=128).save(flat_path, format="PNG")
    mock_photo = MagicMock()
    mock_photo.file_path = flat_path
    mock_photo.id = 20
    mock_db = MagicMock()

    with (
        patch("src.tasks.quality_tasks.get_photo_by_id", return_value=mock_photo),
        patch("src.tasks.quality_tasks.create_quality_issue") as mock_cqi,
        patch("src.tasks.quality_tasks._finish_task"),
        patch("src.tasks.quality_tasks.SessionLocal", return_value=mock_db),
    ):
        from src.tasks.quality_tasks import blur_task
        blur_task.__wrapped__(20, phase="first")
        assert mock_cqi.called
        assert mock_cqi.call_args[0][2] == "blur"


def test_entropy_task_flags_uniform_image(tmp_path):
    uniform_path = _make_jpeg(tmp_path, "uni.jpg", color=(100, 100, 100))
    mock_photo = MagicMock()
    mock_photo.file_path = uniform_path
    mock_photo.id = 30
    mock_db = MagicMock()

    with (
        patch("src.tasks.quality_tasks.get_photo_by_id", return_value=mock_photo),
        patch("src.tasks.quality_tasks.create_quality_issue") as mock_cqi,
        patch("src.tasks.quality_tasks._finish_task"),
        patch("src.tasks.quality_tasks.SessionLocal", return_value=mock_db),
    ):
        from src.tasks.quality_tasks import entropy_task
        entropy_task.__wrapped__(30, phase="first")
        assert mock_cqi.called
        assert mock_cqi.call_args[0][2] == "entropy"


def test_edge_density_task_flags_flat_image(tmp_path):
    flat_path = _make_jpeg(tmp_path, "flat2.jpg", color=(128, 128, 128))
    mock_photo = MagicMock()
    mock_photo.file_path = flat_path
    mock_photo.id = 40
    mock_db = MagicMock()

    with (
        patch("src.tasks.quality_tasks.get_photo_by_id", return_value=mock_photo),
        patch("src.tasks.quality_tasks.create_quality_issue") as mock_cqi,
        patch("src.tasks.quality_tasks._finish_task"),
        patch("src.tasks.quality_tasks.SessionLocal", return_value=mock_db),
    ):
        from src.tasks.quality_tasks import edge_density_task
        edge_density_task.__wrapped__(40, phase="first")
        assert mock_cqi.called
        assert mock_cqi.call_args[0][2] == "edge_density"
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd backend
python -m pytest tests/test_quality_tasks.py -v -k "brightness or blur or entropy or edge_density"
```
Expected: `ModuleNotFoundError: No module named 'src.tasks.quality_tasks'`

- [ ] **Step 3: Create quality_tasks.py**

```python
# backend/src/tasks/quality_tasks.py
"""Phase-1 and phase-3 quality detection tasks — all run on clip_queue (CPU only)."""
from loguru import logger

from src.database import SessionLocal
from src.db_service import get_photo_by_id, delete_job, create_quality_issue
from src.quality_checks import (
    check_brightness,
    check_edge_density,
    check_blur,
    check_entropy,
    check_screenshot,
)
from src.queues.clip_queue import clip_queue


def _run_quality_check(photo_id: int, phase: str, task_name: str, check_fn, issue_type: str, folder_scanner_id=None):
    """Shared runner: open photo, run check_fn, flag if needed, finish task."""
    from src.tasks.utils import _finish_task
    db = SessionLocal()
    try:
        photo = get_photo_by_id(db, photo_id)
        if not photo:
            db.rollback()
            _finish_task(photo_id=photo_id, phase=phase, name=task_name, folder_scanner_id=folder_scanner_id)
            return

        try:
            flagged, score = check_fn(photo.file_path)
            if flagged:
                create_quality_issue(db, photo.id, issue_type, score)
                logger.info(f"[quality] Photo {photo_id} flagged as '{issue_type}' (score={score})")
            db.commit()
        except Exception as check_err:
            logger.warning(f"[quality] {task_name} check failed for photo {photo_id}: {check_err} — skipping")
            db.rollback()

        _finish_task(photo_id=photo_id, phase=phase, name=task_name, folder_scanner_id=folder_scanner_id)

    except Exception as e:
        logger.error(f"[quality] Fatal error in {task_name} for photo {photo_id}: {e}")
        db.rollback()
        try:
            delete_job(db, photo_id, phase)
            db.commit()
        except Exception:
            db.rollback()
            raise
    finally:
        db.close()


@clip_queue.task()
def brightness_task(photo_id: int, phase: str, folder_scanner_id: int = None):
    """Flag photos with abnormal brightness (too dark or overexposed)."""
    _run_quality_check(photo_id, phase, "brightness_task", check_brightness, "brightness", folder_scanner_id)


@clip_queue.task()
def edge_density_task(photo_id: int, phase: str, folder_scanner_id: int = None):
    """Flag featureless / flat photos with very low edge density."""
    _run_quality_check(photo_id, phase, "edge_density_task", check_edge_density, "edge_density", folder_scanner_id)


@clip_queue.task()
def blur_task(photo_id: int, phase: str, folder_scanner_id: int = None):
    """Flag blurry photos via Laplacian variance."""
    _run_quality_check(photo_id, phase, "blur_task", check_blur, "blur", folder_scanner_id)


@clip_queue.task()
def entropy_task(photo_id: int, phase: str, folder_scanner_id: int = None):
    """Flag low-information photos via image entropy."""
    _run_quality_check(photo_id, phase, "entropy_task", check_entropy, "entropy", folder_scanner_id)


@clip_queue.task()
def screenshot_detect_task(photo_id: int, phase: str, folder_scanner_id: int = None):
    """Flag screenshots and UI captures via color-quantization analysis."""
    _run_quality_check(photo_id, phase, "screenshot_detect_task", check_screenshot, "screenshot", folder_scanner_id)
```

- [ ] **Step 4: Run to verify all pass**

```bash
cd backend
python -m pytest tests/test_quality_tasks.py -v
```
Expected: all tests PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/src/tasks/quality_tasks.py backend/tests/test_quality_tasks.py
git commit -m "feat: add brightness, edge_density, blur, entropy, screenshot quality tasks"
```

---

## Task 6: Wire Quality Tasks into Pipeline (phase_logic + _dispatch_tasks)

**Files:**
- Modify: `backend/src/tasks/utils.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_quality_tasks.py`:

```python
def test_phase_logic_first_includes_quality_tasks():
    from src.tasks.utils import phase_logic
    phase, tasks = phase_logic("init")
    assert phase == "first"
    for name in ("brightness_task", "edge_density_task", "blur_task", "entropy_task"):
        assert name in tasks, f"Expected '{name}' in phase-1 tasks"


def test_phase_logic_third_includes_screenshot_task():
    from src.tasks.utils import phase_logic
    phase, tasks = phase_logic("second")
    assert phase == "third"
    assert "screenshot_detect_task" in tasks
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd backend
python -m pytest tests/test_quality_tasks.py -v -k "phase_logic"
```
Expected: FAIL — quality tasks not in phase strings

- [ ] **Step 3: Update utils.py**

In `backend/src/tasks/utils.py`, replace the `phase_logic` function:

```python
def phase_logic(phase: str) -> tuple[str, str]:
    if phase == "init":
        return "first", (
            "metadata_task,auto_tag_clip_task,categorize_photo_task,"
            "vision_task,ocr_task,compute_perceptual_hashes_task,"
            "brightness_task,edge_density_task,blur_task,entropy_task,"
        )
    elif phase == "first":
        return "second", "final_embedding_task,translate_description_task,is_this_document_task,"
    elif phase == "second":
        return "third", "embedding_document_text_task,screenshot_detect_task,"
    return "", ""
```

In `_dispatch_tasks`, add to the import at the top of the function body:

```python
    from .quality_tasks import brightness_task, edge_density_task, blur_task, entropy_task, screenshot_detect_task
```

And add the dispatch cases inside the `for task_name in tasks.split(","):` loop:

```python
        elif task_name == "brightness_task":
            brightness_task(photo_id, phase=phase, folder_scanner_id=folder_scanner_id)
        elif task_name == "edge_density_task":
            edge_density_task(photo_id, phase=phase, folder_scanner_id=folder_scanner_id)
        elif task_name == "blur_task":
            blur_task(photo_id, phase=phase, folder_scanner_id=folder_scanner_id)
        elif task_name == "entropy_task":
            entropy_task(photo_id, phase=phase, folder_scanner_id=folder_scanner_id)
        elif task_name == "screenshot_detect_task":
            screenshot_detect_task(photo_id, phase=phase, folder_scanner_id=folder_scanner_id)
```

- [ ] **Step 4: Run to verify all quality task tests pass**

```bash
cd backend
python -m pytest tests/test_quality_tasks.py -v
```
Expected: all tests PASSED

- [ ] **Step 5: Run full backend test suite to check for regressions**

```bash
cd backend
python -m pytest --ignore=tests/test_e2e_pipeline.py -q
```
Expected: no new failures

- [ ] **Step 6: Commit**

```bash
git add backend/src/tasks/utils.py
git commit -m "feat: wire quality tasks into pipeline phases 1 and 3"
```

---

## Task 7: API Endpoints for Garbage

**Files:**
- Modify: `backend/src/main.py`
- Create: `backend/tests/test_api_garbage.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_api_garbage.py
import sys
from unittest.mock import MagicMock, patch
import sqlalchemy.types

mock_pgvector = MagicMock()
mock_pgvector.sqlalchemy.Vector = lambda size: sqlalchemy.types.JSON()
sys.modules['pgvector'] = mock_pgvector
sys.modules['pgvector.sqlalchemy'] = mock_pgvector.sqlalchemy

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    with patch("src.main.registry"), patch("src.main.watcher_service"):
        from src.main import app
        return TestClient(app)


def test_get_garbage_summary_empty(client):
    with patch("src.main.get_quality_summary", return_value={}):
        resp = client.get("/api/garbage/")
    assert resp.status_code == 200
    assert resp.json() == {"counts": {}}


def test_get_garbage_summary_with_data(client):
    with patch("src.main.get_quality_summary", return_value={"blur": 3, "no_exif": 7}):
        resp = client.get("/api/garbage/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["counts"]["blur"] == 3
    assert data["counts"]["no_exif"] == 7


def test_get_garbage_photos_returns_paginated(client):
    from unittest.mock import MagicMock as MM
    mock_photo = MM()
    mock_photo.id = 1
    mock_photo.file_path = "/tmp/a.jpg"
    mock_photo.hash = "abc"
    mock_photo.description = None
    mock_photo.is_doc = False
    mock_photo.ocr_text = None
    mock_photo.created_at = None
    mock_photo.captured_at = None
    mock_photo.file_created_at = None
    mock_photo.translated_description = None
    mock_photo.tags_rel = []
    mock_photo.categories_rel = []
    mock_photo.camera = None
    mock_photo.geoposition = None
    mock_photo.image_width = None
    mock_photo.image_height = None
    mock_photo.iso = None
    mock_photo.aperture = None
    mock_photo.focal_length = None
    mock_photo.shutter_speed = None
    mock_photo.offset_time = None
    mock_photo.is_archived = False

    with patch("src.main.get_photos_by_issue_type", return_value=([mock_photo], 1)):
        resp = client.get("/api/garbage/blur/photos/?skip=0&limit=20")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1


def test_get_garbage_photos_unknown_type_returns_empty(client):
    with patch("src.main.get_photos_by_issue_type", return_value=([], 0)):
        resp = client.get("/api/garbage/nonexistent/photos/")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd backend
python -m pytest tests/test_api_garbage.py -v
```
Expected: 404 Not Found (routes don't exist yet)

- [ ] **Step 3: Add endpoints to main.py**

Add to the imports in `backend/src/main.py`:

```python
from src.db_service import (
    ...existing imports...,
    get_quality_summary,
    get_photos_by_issue_type,
)
```

Add these two endpoints (after the existing duplicates endpoints):

```python
@app.get("/api/garbage/", tags=["Garbage"])
def get_garbage_summary_endpoint(db: Session = Depends(get_db)) -> dict:
    return {"counts": get_quality_summary(db)}


@app.get("/api/garbage/{issue_type}/photos/", tags=["Garbage"])
def get_garbage_photos_endpoint(
    issue_type: str,
    skip: int = Query(0),
    limit: int = Query(20),
    db: Session = Depends(get_db),
) -> PaginatedResponse[PhotoSchema]:
    photos, total = get_photos_by_issue_type(db, issue_type, skip=skip, limit=limit)
    return PaginatedResponse(
        items=photos,
        total=total,
        page=(skip // limit) + 1 if limit > 0 else 1,
        size=limit,
    )
```

- [ ] **Step 4: Run to verify all pass**

```bash
cd backend
python -m pytest tests/test_api_garbage.py -v
```
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/src/main.py backend/tests/test_api_garbage.py
git commit -m "feat: add /api/garbage/ summary and photo-list endpoints"
```

---

## Task 8: Frontend — PhotoCard with Optional Action Buttons

**Files:**
- Modify: `frontend/src/components/photos/PhotoCard.tsx`
- Modify: `frontend/src/components/photos/PhotoCard.css`
- Modify: `frontend/src/components/photos/__tests__/PhotoCard.test.tsx`

- [ ] **Step 1: Write the failing test**

Add to `frontend/src/components/photos/__tests__/PhotoCard.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { PhotoCard } from '../PhotoCard'
import { makePhoto } from '@/test/factories'

const renderCard = (props = {}) =>
    render(
        <MemoryRouter>
            <PhotoCard photo={makePhoto()} {...props} />
        </MemoryRouter>
    )

describe('PhotoCard action buttons', () => {
    it('shows no action buttons when no handlers provided', () => {
        renderCard()
        expect(screen.queryByRole('button', { name: /archive/i })).toBeNull()
        expect(screen.queryByRole('button', { name: /delete/i })).toBeNull()
    })

    it('shows Archive button when onArchive provided', () => {
        renderCard({ onArchive: vi.fn() })
        expect(screen.getByRole('button', { name: /archive/i })).toBeInTheDocument()
    })

    it('shows Delete button when onDelete provided', () => {
        renderCard({ onDelete: vi.fn() })
        expect(screen.getByRole('button', { name: /delete/i })).toBeInTheDocument()
    })

    it('calls onArchive when Archive button clicked', () => {
        const onArchive = vi.fn()
        renderCard({ onArchive })
        fireEvent.click(screen.getByRole('button', { name: /archive/i }))
        expect(onArchive).toHaveBeenCalledOnce()
    })

    it('calls onDelete when Delete button clicked', () => {
        const onDelete = vi.fn()
        renderCard({ onDelete })
        fireEvent.click(screen.getByRole('button', { name: /delete/i }))
        expect(onDelete).toHaveBeenCalledOnce()
    })

    it('does not navigate when action button clicked', () => {
        const onArchive = vi.fn()
        renderCard({ onArchive })
        fireEvent.click(screen.getByRole('button', { name: /archive/i }))
        // navigation would throw in MemoryRouter — no throw = pass
    })
})
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd frontend
npx vitest run src/components/photos/__tests__/PhotoCard.test.tsx
```
Expected: FAIL — buttons not found

- [ ] **Step 3: Update PhotoCard.tsx**

Replace `frontend/src/components/photos/PhotoCard.tsx` with:

```tsx
import React from 'react'
import { useNavigate } from 'react-router-dom'
import { Badge } from '@/components/ui/Badge'
import { photoImageUrl } from '@/api/images'
import type { Photo, Job } from '@/types/api'
import './PhotoCard.css'

interface PhotoCardProps {
    photo: Photo
    job?: Job | null
    onArchive?: () => void
    onDelete?: () => void
}

export function PhotoCard({ photo, job, onArchive, onDelete }: PhotoCardProps) {
    const navigate = useNavigate()

    const filename =
        photo?.file_path?.split('/').pop() ?? photo?.file_path ?? 'Unknown file'

    const topTag = photo?.tags?.[0]

    const hasActions = onArchive !== undefined || onDelete !== undefined

    return (
        <article
            className="photo-card"
            onClick={() => navigate(`/photo/${photo.id}`)}
            role="article"
        >
            <div className="photo-card__image-wrap">
                <img
                    src={photoImageUrl(photo.file_path)}
                    alt={filename}
                    className="photo-card__image"
                />
            </div>

            <div className="photo-card__body">
                <p className="photo-card__name">{filename}</p>

                <div className="photo-card__badges">
                    {job && <Badge variant="processing">Processing…</Badge>}
                    {photo?.is_doc && <Badge variant="doc">Document</Badge>}
                    {topTag?.tag?.name && (
                        <Badge variant="default">{topTag.tag.name}</Badge>
                    )}
                </div>

                {typeof topTag?.confidence_score === 'number' && (
                    <div className="photo-card__confidence">
                        <div
                            className="photo-card__confidence-bar"
                            style={{
                                width: `${Math.round(
                                    (topTag.confidence_score || 0) * 100
                                )}%`,
                            }}
                        />
                    </div>
                )}

                {hasActions && (
                    <div className="photo-card__actions">
                        {onArchive && (
                            <button
                                className="photo-card__action-btn photo-card__action-btn--archive"
                                onClick={(e) => { e.stopPropagation(); onArchive() }}
                            >
                                Archive
                            </button>
                        )}
                        {onDelete && (
                            <button
                                className="photo-card__action-btn photo-card__action-btn--delete"
                                onClick={(e) => { e.stopPropagation(); onDelete() }}
                            >
                                Delete
                            </button>
                        )}
                    </div>
                )}
            </div>
        </article>
    )
}
```

- [ ] **Step 4: Add action button styles to PhotoCard.css**

Append to `frontend/src/components/photos/PhotoCard.css`:

```css
.photo-card__actions {
    display: flex;
    gap: 6px;
    margin-top: 4px;
}

.photo-card__action-btn {
    flex: 1;
    font-size: 11px;
    font-weight: 500;
    padding: 4px 6px;
    border-radius: 5px;
    cursor: pointer;
    transition: background 0.15s, border-color 0.15s;
    font-family: var(--font-sans);
}

.photo-card__action-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.photo-card__action-btn--archive {
    background: rgba(124, 111, 255, 0.12);
    color: var(--color-accent);
    border: 1px solid rgba(124, 111, 255, 0.3);
}

.photo-card__action-btn--archive:hover:not(:disabled) {
    background: rgba(124, 111, 255, 0.22);
    border-color: rgba(124, 111, 255, 0.5);
}

.photo-card__action-btn--delete {
    background: rgba(239, 68, 68, 0.12);
    color: #f87171;
    border: 1px solid rgba(239, 68, 68, 0.3);
}

.photo-card__action-btn--delete:hover:not(:disabled) {
    background: rgba(239, 68, 68, 0.22);
    border-color: rgba(239, 68, 68, 0.5);
}
```

- [ ] **Step 5: Run to verify all pass**

```bash
cd frontend
npx vitest run src/components/photos/__tests__/PhotoCard.test.tsx
```
Expected: all tests PASSED

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/photos/PhotoCard.tsx frontend/src/components/photos/PhotoCard.css frontend/src/components/photos/__tests__/PhotoCard.test.tsx
git commit -m "feat: add optional onArchive/onDelete action buttons to PhotoCard"
```

---

## Task 9: Frontend — API Client Functions

**Files:**
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Write the failing test**

Add to `frontend/src/api/__tests__/client.test.ts`:

```ts
import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest'
import { server } from '@/test/server'
import { http, HttpResponse } from 'msw'
import { getGarbageSummary, getGarbagePhotos } from '@/api/client'
import { makePaginatedPhotos } from '@/test/factories'

beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

describe('garbage API client', () => {
    it('getGarbageSummary returns counts', async () => {
        server.use(
            http.get('http://localhost:8000/api/garbage/', () =>
                HttpResponse.json({ counts: { blur: 3, no_exif: 1 } })
            )
        )
        const result = await getGarbageSummary()
        expect(result.counts.blur).toBe(3)
        expect(result.counts.no_exif).toBe(1)
    })

    it('getGarbagePhotos returns paginated photos', async () => {
        server.use(
            http.get('http://localhost:8000/api/garbage/blur/photos/', () =>
                HttpResponse.json(makePaginatedPhotos())
            )
        )
        const result = await getGarbagePhotos('blur')
        expect(result.total).toBeGreaterThanOrEqual(1)
    })
})
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd frontend
npx vitest run src/api/__tests__/client.test.ts
```
Expected: `getGarbageSummary is not a function`

- [ ] **Step 3: Add to client.ts**

Append to `frontend/src/api/client.ts`:

```ts
export interface GarbageSummary {
    counts: Record<string, number>
}

export async function getGarbageSummary(): Promise<GarbageSummary> {
    return apiFetch<GarbageSummary>('/api/garbage/')
}

export async function getGarbagePhotos(
    issueType: string,
    skip = 0,
    limit = 20,
): Promise<PaginatedPhotos> {
    const qs = `?skip=${skip}&limit=${limit}`
    return apiFetch<PaginatedPhotos>(`/api/garbage/${issueType}/photos/${qs}`)
}
```

Also add `PaginatedPhotos` to the import from `@/types/api` at the top of `client.ts`:

```ts
import type {
    Photo, PaginatedPhotos, Watcher, Job,
    SystemStatus, SearchResult, ChatResponse, FolderScanner,
    AIModelConfig, AIModelConfigUpdate
} from '@/types/api'
```

(`PaginatedPhotos` is already imported — verify it's in the import list; add it if missing.)

- [ ] **Step 4: Run to verify all pass**

```bash
cd frontend
npx vitest run src/api/__tests__/client.test.ts
```
Expected: all tests PASSED

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/api/__tests__/client.test.ts
git commit -m "feat: add getGarbageSummary and getGarbagePhotos API client functions"
```

---

## Task 10: Frontend — GarbageBadPhotoPage

**Files:**
- Create: `frontend/src/pages/GarbageBadPhotoPage.tsx`
- Create: `frontend/src/pages/GarbageBadPhotoPage.css`
- Create: `frontend/src/pages/__tests__/GarbageBadPhotoPage.test.tsx`

- [ ] **Step 1: Write the failing tests**

```tsx
// frontend/src/pages/__tests__/GarbageBadPhotoPage.test.tsx
import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { server } from '@/test/server'
import { http, HttpResponse } from 'msw'
import { makePaginatedPhotos, makePhoto } from '@/test/factories'
import { GarbageBadPhotoPage } from '../GarbageBadPhotoPage'

vi.mock('@/api/base', () => ({ getBaseUrl: async () => 'http://localhost:8000' }))

beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

const renderPage = () =>
    render(
        <MemoryRouter>
            <GarbageBadPhotoPage />
        </MemoryRouter>
    )

function mockSummary(counts: Record<string, number>) {
    server.use(
        http.get('http://localhost:8000/api/garbage/', () =>
            HttpResponse.json({ counts })
        )
    )
}

function mockPhotos(issueType: string, photos = [makePhoto()]) {
    server.use(
        http.get(`http://localhost:8000/api/garbage/${issueType}/photos/`, () =>
            HttpResponse.json(makePaginatedPhotos(photos))
        )
    )
}

describe('GarbageBadPhotoPage', () => {
    it('renders the page title', async () => {
        mockSummary({})
        renderPage()
        await waitFor(() =>
            expect(screen.getByText(/Garbage/i)).toBeInTheDocument()
        )
    })

    it('shows four category sections', async () => {
        mockSummary({})
        renderPage()
        await waitFor(() => {
            expect(screen.getByText(/Technical Garbage/i)).toBeInTheDocument()
            expect(screen.getByText(/Semantic Garbage/i)).toBeInTheDocument()
            expect(screen.getByText(/Temporary Garbage/i)).toBeInTheDocument()
            expect(screen.getByText(/Subjective Garbage/i)).toBeInTheDocument()
        })
    })

    it('shows blur count badge when summary has blur data', async () => {
        mockSummary({ blur: 5 })
        renderPage()
        await waitFor(() => expect(screen.getByText('5')).toBeInTheDocument())
    })

    it('expands blur row and shows photo cards', async () => {
        mockSummary({ blur: 1 })
        mockPhotos('blur')
        renderPage()
        await waitFor(() => screen.getByText('1'))
        fireEvent.click(screen.getByText(/Blurry/i))
        await waitFor(() =>
            expect(screen.getAllByRole('article')).toHaveLength(1)
        )
    })

    it('shows placeholder text for semantic, temporary, subjective sections', async () => {
        mockSummary({})
        renderPage()
        await waitFor(() =>
            expect(screen.getAllByText(/Coming soon/i).length).toBeGreaterThanOrEqual(3)
        )
    })
})
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd frontend
npx vitest run src/pages/__tests__/GarbageBadPhotoPage.test.tsx
```
Expected: `Cannot find module '../GarbageBadPhotoPage'`

- [ ] **Step 3: Create GarbageBadPhotoPage.tsx**

```tsx
// frontend/src/pages/GarbageBadPhotoPage.tsx
import React, { useCallback, useEffect, useState } from 'react'
import { getGarbageSummary, getGarbagePhotos, archivePhoto, deletePhoto } from '@/api/client'
import type { GarbageSummary } from '@/api/client'
import type { PaginatedPhotos } from '@/types/api'
import { PhotoCard } from '@/components/photos/PhotoCard'
import { Spinner } from '@/components/ui/Spinner'
import './GarbageBadPhotoPage.css'

interface IssueRow {
    type: string
    label: string
}

const TECHNICAL_ISSUES: IssueRow[] = [
    { type: 'thumbnail',    label: 'Thumbnails (resolution too small)' },
    { type: 'no_exif',     label: 'No EXIF (possible internet copy)' },
    { type: 'brightness',  label: 'Abnormal brightness' },
    { type: 'edge_density',label: 'Low edge density (featureless)' },
    { type: 'blur',        label: 'Blurry (Laplacian)' },
    { type: 'entropy',     label: 'Low entropy (low information)' },
    { type: 'screenshot',  label: 'Screenshots (UI detected)' },
]

function IssueSection({ issue, count }: { issue: IssueRow; count: number }) {
    const [expanded, setExpanded] = useState(false)
    const [data, setData] = useState<PaginatedPhotos | null>(null)
    const [loading, setLoading] = useState(false)
    const [ids, setIds] = useState<Set<number>>(new Set())

    async function expand() {
        if (expanded) { setExpanded(false); return }
        setExpanded(true)
        if (data) return
        setLoading(true)
        try {
            const result = await getGarbagePhotos(issue.type, 0, 50)
            setData(result)
            setIds(new Set(result.items.map(p => p.id)))
        } finally {
            setLoading(false)
        }
    }

    function removeCard(id: number) {
        setIds(prev => { const next = new Set(prev); next.delete(id); return next })
    }

    async function handleArchive(id: number) {
        await archivePhoto(id)
        removeCard(id)
    }

    async function handleDelete(id: number) {
        await deletePhoto(id)
        removeCard(id)
    }

    const visiblePhotos = data?.items.filter(p => ids.has(p.id)) ?? []

    return (
        <div className="gbp-issue">
            <button className="gbp-issue__row" onClick={expand}>
                <span className="gbp-issue__label">{issue.label}</span>
                {count > 0 && (
                    <span className="gbp-issue__count">{count}</span>
                )}
                <span className="gbp-issue__chevron">{expanded ? '▲' : '▼'}</span>
            </button>

            {expanded && (
                <div className="gbp-issue__cards">
                    {loading && <Spinner />}
                    {!loading && visiblePhotos.length === 0 && (
                        <p className="gbp-issue__empty">No photos flagged.</p>
                    )}
                    {!loading && visiblePhotos.map(photo => (
                        <PhotoCard
                            key={photo.id}
                            photo={photo}
                            onArchive={() => handleArchive(photo.id)}
                            onDelete={() => handleDelete(photo.id)}
                        />
                    ))}
                </div>
            )}
        </div>
    )
}

interface PlaceholderSectionProps { title: string }

function PlaceholderSection({ title }: PlaceholderSectionProps) {
    return (
        <section className="gbp-section">
            <h2 className="gbp-section__heading">{title}</h2>
            <p className="gbp-section__placeholder">Coming soon</p>
        </section>
    )
}

export function GarbageBadPhotoPage() {
    const [summary, setSummary] = useState<GarbageSummary | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    const load = useCallback(async () => {
        setLoading(true)
        setError(null)
        try {
            setSummary(await getGarbageSummary())
        } catch {
            setError('Failed to load garbage summary')
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => { load() }, [load])

    if (loading) return <div className="gbp-page"><Spinner /></div>
    if (error) return <div className="gbp-page gbp-page--error">{error}</div>

    const counts = summary?.counts ?? {}

    return (
        <div className="gbp-page">
            <h1 className="gbp-page__title">Garbage &amp; Bad Photos</h1>

            <section className="gbp-section">
                <h2 className="gbp-section__heading">Technical Garbage</h2>
                <div className="gbp-issues">
                    {TECHNICAL_ISSUES.map(issue => (
                        <IssueSection
                            key={issue.type}
                            issue={issue}
                            count={counts[issue.type] ?? 0}
                        />
                    ))}
                </div>
            </section>

            <div className="gbp-divider" />
            <PlaceholderSection title="Semantic Garbage" />
            <div className="gbp-divider" />
            <PlaceholderSection title="Temporary Garbage" />
            <div className="gbp-divider" />
            <PlaceholderSection title="Subjective Garbage" />
        </div>
    )
}
```

- [ ] **Step 4: Create GarbageBadPhotoPage.css**

```css
/* frontend/src/pages/GarbageBadPhotoPage.css */
.gbp-page {
    padding: 24px;
    max-width: 960px;
    margin: 0 auto;
}

.gbp-page--error {
    color: #f87171;
    padding: 40px 24px;
}

.gbp-page__title {
    font-size: 22px;
    font-weight: 600;
    color: var(--color-text);
    margin: 0 0 24px;
}

.gbp-section {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.gbp-section__heading {
    font-size: 15px;
    font-weight: 600;
    color: var(--color-text);
    margin: 0 0 8px;
}

.gbp-section__placeholder {
    color: var(--color-text-dim, #9999b5);
    font-size: 13px;
    margin: 0;
    padding: 12px 0;
}

.gbp-divider {
    height: 1px;
    background: var(--color-border);
    margin: 24px 0;
}

.gbp-issues {
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.gbp-issue {
    border: 1px solid var(--color-border);
    border-radius: 8px;
    overflow: hidden;
}

.gbp-issue__row {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 14px;
    background: var(--color-surface);
    border: none;
    cursor: pointer;
    text-align: left;
    font-family: var(--font-sans);
    color: var(--color-text);
    font-size: 13px;
    font-weight: 500;
    transition: background 0.12s;
}

.gbp-issue__row:hover {
    background: var(--color-surface-2);
}

.gbp-issue__label {
    flex: 1;
}

.gbp-issue__count {
    font-size: 12px;
    font-weight: 500;
    background: var(--color-surface-2);
    border: 1px solid var(--color-border);
    color: var(--color-text-dim, #9999b5);
    padding: 2px 8px;
    border-radius: 12px;
}

.gbp-issue__chevron {
    font-size: 10px;
    color: var(--color-text-dim, #9999b5);
}

.gbp-issue__cards {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: 12px;
    padding: 14px;
    background: var(--color-surface-2);
    border-top: 1px solid var(--color-border);
}

.gbp-issue__empty {
    color: var(--color-text-dim, #9999b5);
    font-size: 13px;
    margin: 0;
    grid-column: 1 / -1;
}
```

- [ ] **Step 5: Run to verify all tests pass**

```bash
cd frontend
npx vitest run src/pages/__tests__/GarbageBadPhotoPage.test.tsx
```
Expected: all tests PASSED

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/GarbageBadPhotoPage.tsx frontend/src/pages/GarbageBadPhotoPage.css frontend/src/pages/__tests__/GarbageBadPhotoPage.test.tsx
git commit -m "feat: add GarbageBadPhotoPage with expandable technical issue sections"
```

---

## Task 11: Frontend — Router + Sidebar Integration

**Files:**
- Modify: `frontend/src/pages/AppRoutes.tsx`
- Modify: `frontend/src/components/ui/Sidebar.tsx`

- [ ] **Step 1: Write the failing test**

Add to `frontend/src/components/ui/__tests__/Sidebar.test.tsx`:

```tsx
it('renders garbage link', () => {
    render(
        <MemoryRouter>
            <Sidebar state="full" />
        </MemoryRouter>
    )
    expect(screen.getByText('Garbage')).toBeInTheDocument()
})
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd frontend
npx vitest run src/components/ui/__tests__/Sidebar.test.tsx
```
Expected: FAIL — "Garbage" not found

- [ ] **Step 3: Update AppRoutes.tsx**

```tsx
import React from 'react'
import { Routes, Route } from 'react-router-dom'
import { GalleryPage } from './GalleryPage'
import { SearchPage } from './SearchPage'
import { DocumentsPage } from './DocumentsPage'
import { ChatPage } from './ChatPage'
import { SettingsPage } from './SettingsPage'
import { PhotoDetailPage } from './PhotoDetailPage'
import { JobProcessingPage } from './JobProcessingPage'
import { FoldersPage } from './FoldersPage'
import { ModelsPage } from './ModelsPage'
import { DuplicatesPage } from './DuplicatesPage'
import { GarbageBadPhotoPage } from './GarbageBadPhotoPage'

export function AppRoutes() {
    return (
        <Routes>
            <Route path="/" element={<GalleryPage />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/documents" element={<DocumentsPage />} />
            <Route path="/duplicates" element={<DuplicatesPage />} />
            <Route path="/garbage" element={<GarbageBadPhotoPage />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/photo/:id" element={<PhotoDetailPage />} />
            <Route path="/processing" element={<JobProcessingPage />} />
            <Route path="/folders" element={<FoldersPage />} />
            <Route path="/models" element={<ModelsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
        </Routes>
    )
}
```

- [ ] **Step 4: Update Sidebar.tsx**

In `frontend/src/components/ui/Sidebar.tsx`, add the garbage link to the `links` array after the duplicates entry:

```ts
const links = [
    { to: '/', label: 'Gallery', icon: '🖼️', end: true },
    { to: '/search', label: 'Search', icon: '🔍' },
    { to: '/documents', label: 'Documents', icon: '📄' },
    { to: '/duplicates', label: 'Duplicates', icon: '⊕' },
    { to: '/garbage', label: 'Garbage', icon: '🗑️' },
    { to: '/chat', label: 'Agent AI(Chat)', icon: '💬' },
    { to: '/processing', label: 'Video Processing', icon: '📹' },
    { to: '/folders', label: 'Folders', icon: '📁' },
    { to: '/models', label: 'Models', icon: '🤖' },
    { to: '/settings', label: 'Settings', icon: '⚙️' },
]
```

- [ ] **Step 5: Run to verify tests pass**

```bash
cd frontend
npx vitest run src/components/ui/__tests__/Sidebar.test.tsx
```
Expected: all tests PASSED

- [ ] **Step 6: Run full frontend test suite**

```bash
cd frontend
npx vitest run
```
Expected: no regressions

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/AppRoutes.tsx frontend/src/components/ui/Sidebar.tsx frontend/src/components/ui/__tests__/Sidebar.test.tsx
git commit -m "feat: add /garbage route and sidebar link for GarbageBadPhotoPage"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] Technical garbage: resolution (Task 4), EXIF (Task 4), brightness (Task 5), edge density (Task 5), blur (Task 5), entropy (Task 5), screenshot (Task 5/6)
- [x] DB table `photo_quality_issues` (Task 1)
- [x] Tasks in correct pipeline phases: resolution+EXIF in metadata_task/phase-1, brightness/edge/blur/entropy in phase-1, screenshot in phase-3 (Tasks 4–6)
- [x] API endpoints: GET /api/garbage/ and GET /api/garbage/{issue_type}/photos/ (Task 7)
- [x] PhotoCard archive/delete buttons (Task 8)
- [x] GarbageBadPhotoPage with 4 sections, 3 placeholders (Task 10)
- [x] Sidebar entry + router (Task 11)
- [x] Optimistic card removal on archive/delete (IssueSection.removeCard)

**Placeholder scan:** none found.

**Type consistency:**
- `create_quality_issue(db, photo_id, issue_type, score)` — used consistently in Tasks 2, 4, 5
- `get_quality_summary(db)` → `dict[str, int]` — matches API response `{"counts": ...}`
- `get_photos_by_issue_type(db, issue_type, skip, limit)` → `tuple[list[Photo], int]` — matches PaginatedResponse usage
- `GarbageSummary.counts: Record<string, number>` — matches backend `{"counts": {}}`
- `getGarbagePhotos` returns `PaginatedPhotos` — matches `data.items` usage in page component
