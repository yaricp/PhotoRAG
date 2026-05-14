"""
Shared DB config reader for Huey worker processes.

Uses plain sqlite3 — no SQLAlchemy, no app-level imports — so it stays
lightweight and avoids circular imports inside worker processes.

Each queue file calls:
    model_name = get_model_name_from_db(DB_PATH, "clip", default="ViT-B-32")
    config     = read_model_config_from_db(DB_PATH, "vision")  # -> dict | None
"""
import os
import sqlite3
from loguru import logger


def read_model_config_from_db(db_path: str, model_type: str) -> dict | None:
    """
    Read mode and model_name for model_type from ai_model_configs table.

    Returns {"model_name": ..., "mode": ...} or None if:
    - the DB file does not exist
    - the table does not exist
    - no row for model_type found
    """
    try:
        if not os.path.exists(db_path):
            return None
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT model_name, mode FROM ai_model_configs WHERE type = ?",
            (model_type,)
        ).fetchone()
        conn.close()
        if row:
            return {"model_name": row[0], "mode": row[1]}
        return None
    except Exception as exc:
        logger.warning(f"[queue_config] Could not read config for '{model_type}': {exc}")
        return None


def get_model_name_from_db(db_path: str, model_type: str, default: str) -> str:
    """
    Return the model_name from DB, falling back to default if unavailable.
    """
    cfg = read_model_config_from_db(db_path, model_type)
    if cfg and cfg.get("model_name"):
        return cfg["model_name"]
    logger.warning(
        f"[queue_config] No DB config for '{model_type}', using default: {default!r}"
    )
    return default
