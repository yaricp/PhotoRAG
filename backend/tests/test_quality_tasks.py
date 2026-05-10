# backend/tests/test_quality_tasks.py
"""
Tests for quality detection tasks.
Uses unittest.mock to avoid real Huey queues and DB connections.
"""
import sys
from unittest.mock import MagicMock, patch
import sqlalchemy.types

mock_pgvector = MagicMock()
mock_pgvector.sqlalchemy.Vector = lambda size: sqlalchemy.types.JSON()
sys.modules['pgvector'] = mock_pgvector
sys.modules['pgvector.sqlalchemy'] = mock_pgvector.sqlalchemy

# Mock heavy deps unavailable in the test environment
for _mod in [
    'sqlite_vec', 'src.database', 'src.vector_db_services', 'src.config',
    'src.ai', 'src.ai.registry', 'src.ai.prompts',
    'src.queues', 'src.queues.folder_scan_queue', 'src.queues.clip_queue',
    'src.queues.vision_queue', 'src.queues.embedding_queue',
    'src.queues.translation_queue',
    'src.tasks.utils', 'src.tasks.vision_tasks', 'src.tasks.embedding_tasks',
    'src.tasks.translation_tasks',
    'imagehash',
]:
    sys.modules.setdefault(_mod, MagicMock())

# Also stub src.geo so GeoEnricher lazy import inside metadata_task works
_mock_geo = MagicMock()
sys.modules.setdefault('src.geo', _mock_geo)

import pytest
from PIL import Image


def _make_jpeg(tmp_path, name="test.jpg", size=(800, 600), color=(128, 128, 128)) -> str:
    path = str(tmp_path / name)
    Image.new("RGB", size, color=color).save(path, format="JPEG")
    return path


def _import_clip_tasks():
    """Import clip_tasks fresh, with Huey decorator stubbed out."""
    sys.modules['src.queues.clip_queue'].clip_queue.task.return_value = lambda f: f
    saved = sys.modules.pop('src.tasks', None)
    sys.modules.pop('src.tasks.clip_tasks', None)
    import src.tasks.clip_tasks as m
    if saved is not None:
        sys.modules['src.tasks'] = saved
    return m


def _import_quality_tasks():
    """Import quality_tasks fresh, with Huey decorator stubbed out."""
    sys.modules['src.queues.clip_queue'].clip_queue.task.return_value = lambda f: f
    saved = sys.modules.pop('src.tasks', None)
    sys.modules.pop('src.tasks.quality_tasks', None)
    import src.tasks.quality_tasks as m
    if saved is not None:
        sys.modules['src.tasks'] = saved
    return m


# ── metadata_task resolution + EXIF checks ─────────────────────────────────

def test_metadata_task_flags_thumbnail(tmp_path):
    """metadata_task creates a 'thumbnail' quality issue for a very small image."""
    small_path = _make_jpeg(tmp_path, "small.jpg", size=(50, 50))

    mock_photo = MagicMock()
    mock_photo.file_path = small_path
    mock_photo.id = 1
    mock_photo.image_width = None
    mock_photo.image_height = None

    mock_db = MagicMock()
    task_mod = _import_clip_tasks()

    # GeoEnricher is imported lazily from src.geo inside metadata_task
    mock_geo_instance = MagicMock()
    mock_geo_instance.geocode_photo.return_value = {}
    sys.modules['src.geo'].GeoEnricher.return_value = mock_geo_instance

    # _finish_task is imported lazily from src.tasks.utils
    sys.modules['src.tasks.utils']._finish_task = MagicMock()

    with (
        patch.object(task_mod, "get_photo_by_id", return_value=mock_photo),
        patch.object(task_mod, "extract_exif", return_value={"Make": "Apple"}),
        patch.object(task_mod, "parse_datetime", return_value=None),
        patch.object(task_mod, "get_or_create_camera"),
        patch.object(task_mod, "update_photo_geoposition"),
        patch.object(task_mod, "create_quality_issue") as mock_create_qi,
        patch.object(task_mod, "SessionLocal", return_value=mock_db),
    ):
        task_mod.metadata_task(1, phase="first")

    issue_types = [c.args[2] for c in mock_create_qi.call_args_list]
    assert "thumbnail" in issue_types


def test_metadata_task_flags_no_exif(tmp_path):
    """metadata_task creates a 'no_exif' quality issue when EXIF is empty."""
    path = _make_jpeg(tmp_path, "no_exif.jpg", size=(800, 600))

    mock_photo = MagicMock()
    mock_photo.file_path = path
    mock_photo.id = 2

    mock_db = MagicMock()
    task_mod = _import_clip_tasks()

    mock_geo_instance = MagicMock()
    mock_geo_instance.geocode_photo.return_value = {}
    sys.modules['src.geo'].GeoEnricher.return_value = mock_geo_instance
    sys.modules['src.tasks.utils']._finish_task = MagicMock()

    with (
        patch.object(task_mod, "get_photo_by_id", return_value=mock_photo),
        patch.object(task_mod, "extract_exif", return_value={}),
        patch.object(task_mod, "parse_datetime", return_value=None),
        patch.object(task_mod, "create_quality_issue") as mock_create_qi,
        patch.object(task_mod, "SessionLocal", return_value=mock_db),
    ):
        task_mod.metadata_task(2, phase="first")

    issue_types = [c.args[2] for c in mock_create_qi.call_args_list]
    assert "no_exif" in issue_types


# ── brightness_task ─────────────────────────────────────────────────────────

def test_brightness_task_flags_dark_image(tmp_path):
    dark_path = _make_jpeg(tmp_path, "dark.jpg", color=(5, 5, 5))
    mock_photo = MagicMock()
    mock_photo.file_path = dark_path
    mock_photo.id = 10
    mock_db = MagicMock()

    task_mod = _import_quality_tasks()
    # _finish_task is imported lazily from src.tasks.utils inside _run_quality_check
    sys.modules['src.tasks.utils']._finish_task = MagicMock()

    with (
        patch.object(task_mod, "get_photo_by_id", return_value=mock_photo),
        patch.object(task_mod, "create_quality_issue") as mock_cqi,
        patch.object(task_mod, "SessionLocal", return_value=mock_db),
    ):
        task_mod.brightness_task(10, phase="first")
        assert mock_cqi.called
        assert mock_cqi.call_args[0][2] == "brightness"


def test_brightness_task_skips_normal_image(tmp_path):
    normal_path = _make_jpeg(tmp_path, "normal.jpg", color=(128, 128, 128))
    mock_photo = MagicMock()
    mock_photo.file_path = normal_path
    mock_photo.id = 11
    mock_db = MagicMock()

    task_mod = _import_quality_tasks()
    sys.modules['src.tasks.utils']._finish_task = MagicMock()

    with (
        patch.object(task_mod, "get_photo_by_id", return_value=mock_photo),
        patch.object(task_mod, "create_quality_issue") as mock_cqi,
        patch.object(task_mod, "SessionLocal", return_value=mock_db),
    ):
        task_mod.brightness_task(11, phase="first")
        assert not mock_cqi.called


# ── blur_task ───────────────────────────────────────────────────────────────

def test_blur_task_flags_uniform_image(tmp_path):
    flat_path = str(tmp_path / "flat.png")
    Image.new("L", (100, 100), color=128).save(flat_path, format="PNG")
    mock_photo = MagicMock()
    mock_photo.file_path = flat_path
    mock_photo.id = 20
    mock_db = MagicMock()

    task_mod = _import_quality_tasks()
    sys.modules['src.tasks.utils']._finish_task = MagicMock()

    with (
        patch.object(task_mod, "get_photo_by_id", return_value=mock_photo),
        patch.object(task_mod, "create_quality_issue") as mock_cqi,
        patch.object(task_mod, "SessionLocal", return_value=mock_db),
    ):
        task_mod.blur_task(20, phase="first")
        assert mock_cqi.called
        assert mock_cqi.call_args[0][2] == "blur"


# ── entropy_task ────────────────────────────────────────────────────────────

def test_entropy_task_flags_uniform_image(tmp_path):
    uniform_path = _make_jpeg(tmp_path, "uni.jpg", color=(100, 100, 100))
    mock_photo = MagicMock()
    mock_photo.file_path = uniform_path
    mock_photo.id = 30
    mock_db = MagicMock()

    task_mod = _import_quality_tasks()
    sys.modules['src.tasks.utils']._finish_task = MagicMock()

    with (
        patch.object(task_mod, "get_photo_by_id", return_value=mock_photo),
        patch.object(task_mod, "create_quality_issue") as mock_cqi,
        patch.object(task_mod, "SessionLocal", return_value=mock_db),
    ):
        task_mod.entropy_task(30, phase="first")
        assert mock_cqi.called
        assert mock_cqi.call_args[0][2] == "entropy"


# ── edge_density_task ───────────────────────────────────────────────────────

def test_edge_density_task_flags_flat_image(tmp_path):
    flat_path = _make_jpeg(tmp_path, "flat2.jpg", color=(128, 128, 128))
    mock_photo = MagicMock()
    mock_photo.file_path = flat_path
    mock_photo.id = 40
    mock_db = MagicMock()

    task_mod = _import_quality_tasks()
    sys.modules['src.tasks.utils']._finish_task = MagicMock()

    with (
        patch.object(task_mod, "get_photo_by_id", return_value=mock_photo),
        patch.object(task_mod, "create_quality_issue") as mock_cqi,
        patch.object(task_mod, "SessionLocal", return_value=mock_db),
    ):
        task_mod.edge_density_task(40, phase="first")
        assert mock_cqi.called
        assert mock_cqi.call_args[0][2] == "edge_density"


# ── phase_logic wiring ──────────────────────────────────────────────────────

def _load_utils_fresh():
    """Import the real src.tasks.utils regardless of what other tests have mocked."""
    import importlib, importlib.util, os
    spec = importlib.util.spec_from_file_location(
        "_utils_under_test",
        os.path.join(os.path.dirname(__file__), "..", "src", "tasks", "utils.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    # stub out heavy imports that utils.py pulls in at module level
    mod.__dict__.update({
        "logger": MagicMock(),
        "text": MagicMock(),
        "SessionLocal": MagicMock(),
        "delete_job": MagicMock(),
        "get_or_create_job": MagicMock(),
        "get_folder_scanner": MagicMock(),
        "update_folder_scanner_progress": MagicMock(),
    })
    # patch sys.modules so that top-level imports inside utils.py resolve
    _saved = {}
    for key in ("src.database", "src.db_service", "loguru", "sqlalchemy", "sqlalchemy.text"):
        _saved[key] = sys.modules.get(key)
    sys.modules["loguru"] = MagicMock()
    # execute the module source — only phase_logic is needed, it has no imports
    import ast, types
    with open(spec.origin) as fh:
        source = fh.read()
    # Only exec the phase_logic function definition to keep it isolated
    tree = ast.parse(source)
    fn_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "phase_logic")
    mini_src = ast.unparse(fn_node)
    ns: dict = {}
    exec(compile(mini_src, spec.origin, "exec"), ns)
    return ns["phase_logic"]


def test_phase_logic_first_includes_quality_tasks():
    phase_logic = _load_utils_fresh()
    phase, tasks = phase_logic("init")
    assert phase == "first"
    for name in ("brightness_task", "edge_density_task", "blur_task", "entropy_task"):
        assert name in tasks, f"Expected '{name}' in phase-1 tasks"


def test_phase_logic_third_includes_screenshot_task():
    phase_logic = _load_utils_fresh()
    phase, tasks = phase_logic("second")
    assert phase == "third"
    assert "screenshot_detect_task" in tasks
