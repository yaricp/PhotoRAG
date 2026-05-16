"""
TDD tests for src/data_dir.py — Phase 1: Data Directory Migration.
"""
import os
import sys
import shutil
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# resolve_app_data_dir()
# ---------------------------------------------------------------------------

def test_resolves_macos_path(tmp_path, monkeypatch):
    monkeypatch.delenv("APP_DATA_DIR", raising=False)
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))

    from importlib import reload
    import src.data_dir as data_dir
    reload(data_dir)

    result = data_dir.resolve_app_data_dir()
    assert result == tmp_path / "Library" / "Application Support" / "PhotoRAG"
    assert result.is_dir()


def test_resolves_linux_path(tmp_path, monkeypatch):
    monkeypatch.delenv("APP_DATA_DIR", raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))

    from importlib import reload
    import src.data_dir as data_dir
    reload(data_dir)

    result = data_dir.resolve_app_data_dir()
    assert result == tmp_path / ".local" / "share" / "PhotoRAG"
    assert result.is_dir()


def test_env_override(tmp_path, monkeypatch):
    override = str(tmp_path / "custom_data")
    monkeypatch.setenv("APP_DATA_DIR", override)

    from importlib import reload
    import src.data_dir as data_dir
    reload(data_dir)

    result = data_dir.resolve_app_data_dir()
    assert result == Path(override)
    assert result.is_dir()


# ---------------------------------------------------------------------------
# migrate_legacy_data() — SQLite files
# ---------------------------------------------------------------------------

def _make_sqlite(path: Path) -> None:
    """Create a minimal valid SQLite file."""
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE t (x INTEGER)")
    conn.commit()
    conn.close()


def test_migration_copies_sqlite_files(tmp_path):
    src_root = tmp_path / "project"
    dst_dir = tmp_path / "app_data"
    src_root.mkdir()
    dst_dir.mkdir()

    sqlite_names = [
        "db.sqlite3", "clip.sqlite3", "embedding.sqlite3",
        "folder_scan.sqlite3", "ocr.sqlite3", "translation.sqlite3",
        "vision.sqlite3", "task_results.db",
    ]
    for name in sqlite_names:
        _make_sqlite(src_root / name)

    from src.data_dir import migrate_legacy_data
    migrate_legacy_data(src_root, dst_dir)

    for name in sqlite_names:
        assert (dst_dir / name).exists(), f"{name} was not migrated"


def test_migration_skips_if_already_migrated(tmp_path):
    src_root = tmp_path / "project"
    dst_dir = tmp_path / "app_data"
    src_root.mkdir()
    dst_dir.mkdir()

    _make_sqlite(src_root / "db.sqlite3")
    # Pre-populate destination — migration must not overwrite
    existing = dst_dir / "db.sqlite3"
    existing.write_text("sentinel")

    from src.data_dir import migrate_legacy_data
    migrate_legacy_data(src_root, dst_dir)

    assert existing.read_text() == "sentinel"


def test_migration_skips_missing_source_files(tmp_path):
    src_root = tmp_path / "project"
    dst_dir = tmp_path / "app_data"
    src_root.mkdir()
    dst_dir.mkdir()

    # Only create one file; the rest are absent
    _make_sqlite(src_root / "db.sqlite3")

    from src.data_dir import migrate_legacy_data
    migrate_legacy_data(src_root, dst_dir)

    assert (dst_dir / "db.sqlite3").exists()
    assert not (dst_dir / "clip.sqlite3").exists()


# ---------------------------------------------------------------------------
# migrate_legacy_data() — .env
# ---------------------------------------------------------------------------

def test_migration_copies_dotenv(tmp_path):
    src_root = tmp_path / "project"
    dst_dir = tmp_path / "app_data"
    src_root.mkdir()
    dst_dir.mkdir()

    (src_root / ".env").write_text("API_KEY=abc123\n")

    from src.data_dir import migrate_legacy_data
    migrate_legacy_data(src_root, dst_dir)

    assert (dst_dir / ".env").read_text() == "API_KEY=abc123\n"


def test_migration_skips_dotenv_if_already_exists(tmp_path):
    src_root = tmp_path / "project"
    dst_dir = tmp_path / "app_data"
    src_root.mkdir()
    dst_dir.mkdir()

    (src_root / ".env").write_text("NEW=value\n")
    (dst_dir / ".env").write_text("OLD=value\n")

    from src.data_dir import migrate_legacy_data
    migrate_legacy_data(src_root, dst_dir)

    assert (dst_dir / ".env").read_text() == "OLD=value\n"


# ---------------------------------------------------------------------------
# migrate_legacy_data() — data/*.npy and data/*.hash
# ---------------------------------------------------------------------------

def test_migration_copies_data_npy_files(tmp_path):
    src_root = tmp_path / "project"
    dst_dir = tmp_path / "app_data"
    (src_root / "data").mkdir(parents=True)
    dst_dir.mkdir()

    (src_root / "data" / "tags_features.npy").write_bytes(b"\x93NUMPY")
    (src_root / "data" / "categories_features.npy").write_bytes(b"\x93NUMPY")
    (src_root / "data" / "tags_model.hash").write_text("abc")

    from src.data_dir import migrate_legacy_data
    migrate_legacy_data(src_root, dst_dir)

    assert (dst_dir / "data" / "tags_features.npy").exists()
    assert (dst_dir / "data" / "categories_features.npy").exists()
    assert (dst_dir / "data" / "tags_model.hash").exists()


def test_migration_skips_npy_if_already_exists(tmp_path):
    src_root = tmp_path / "project"
    dst_dir = tmp_path / "app_data"
    (src_root / "data").mkdir(parents=True)
    (dst_dir / "data").mkdir(parents=True)

    (src_root / "data" / "tags_features.npy").write_bytes(b"NEW")
    (dst_dir / "data" / "tags_features.npy").write_bytes(b"OLD")

    from src.data_dir import migrate_legacy_data
    migrate_legacy_data(src_root, dst_dir)

    assert (dst_dir / "data" / "tags_features.npy").read_bytes() == b"OLD"
