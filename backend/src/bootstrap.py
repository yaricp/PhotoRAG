"""
Installer bootstrap reader.

The NSIS Windows installer writes bootstrap.json to the app data directory
after the user selects a language in the installer UI. On the very first
backend startup, this module reads that file and applies the language to
the settings DB, then deletes the file so it only runs once.
"""
import json
from pathlib import Path
from loguru import logger
from sqlalchemy.orm import Session

from src.data_dir import resolve_app_data_dir
from src.db_service import get_setting, set_setting


def _bootstrap_path() -> Path:
    return resolve_app_data_dir() / "bootstrap.json"


def apply_bootstrap_settings(db: Session) -> None:
    """Read bootstrap.json (if present) and apply settings to DB on first launch."""
    path = _bootstrap_path()

    if not path.exists():
        return

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning(f"[bootstrap] Malformed bootstrap.json, skipping: {exc}")
        return

    # Only apply if not already set (truly first launch)
    existing = get_setting(db, "default_language")
    if existing:
        logger.info(f"[bootstrap] Language already set to {existing!r}, skipping bootstrap")
        return

    lang = data.get("default_language", "en")
    set_setting(db, "default_language", lang)
    logger.info(f"[bootstrap] Applied language from installer: {lang!r}")

    # Consume once — delete so it never runs again
    try:
        path.unlink()
    except Exception as exc:
        logger.warning(f"[bootstrap] Could not delete bootstrap.json: {exc}")
