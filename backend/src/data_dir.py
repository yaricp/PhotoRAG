"""
Data directory resolution and legacy migration for Photo Describer 2.

resolve_app_data_dir() returns the platform-appropriate mutable data directory:
  macOS  → ~/Library/Application Support/PhotoRAG/
  Linux  → ~/.local/share/PhotoRAG/
  Override: APP_DATA_DIR env var (used in packaged app and tests)

migrate_legacy_data() is called once on startup to copy existing files from
the project root (dev layout) into APP_DATA_DIR so the app can run from a
read-only .app bundle without losing previously generated data.
"""
import os
import sys
import shutil
import sqlite3
from pathlib import Path

APP_NAME = "PhotoRAG"

_SQLITE_FILES = [
    "db.sqlite3",
    "clip.sqlite3",
    "embedding.sqlite3",
    "folder_scan.sqlite3",
    "ocr.sqlite3",
    "translation.sqlite3",
    "vision.sqlite3",
    "task_results.db",
]


def resolve_app_data_dir() -> Path:
    """Return (and create) the mutable application data directory."""
    if override := os.environ.get("APP_DATA_DIR"):
        path = Path(override)
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / APP_NAME
    else:
        path = Path.home() / ".local" / "share" / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def migrate_legacy_data(project_root: Path, app_data_dir: Path) -> None:
    """
    Idempotently copy legacy dev-layout files into app_data_dir.

    Skips a file if the destination already exists (never overwrites).
    Runs PRAGMA wal_checkpoint(TRUNCATE) before copying SQLite files to
    avoid partial WAL state.  Also copies companion .wal / .shm files.
    """
    for name in _SQLITE_FILES:
        src = project_root / name
        dst = app_data_dir / name
        if dst.exists() or not src.exists():
            continue
        _checkpoint_wal(src)
        shutil.copy2(src, dst)
        for suffix in ("-wal", "-shm"):
            companion = Path(str(src) + suffix)
            if companion.exists():
                shutil.copy2(companion, Path(str(dst) + suffix))

    # .env
    env_src = project_root / ".env"
    env_dst = app_data_dir / ".env"
    if env_src.exists() and not env_dst.exists():
        shutil.copy2(env_src, env_dst)

    # data/ — mutable caches (.npy, .hash, .json)
    data_src = project_root / "data"
    data_dst = app_data_dir / "data"
    if data_src.exists():
        data_dst.mkdir(exist_ok=True)
        for pattern in ("*.npy", "*.hash", "*.json"):
            for f in data_src.glob(pattern):
                dst_f = data_dst / f.name
                if not dst_f.exists():
                    shutil.copy2(f, dst_f)


def _checkpoint_wal(db_path: Path) -> None:
    try:
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.close()
    except Exception:
        pass
