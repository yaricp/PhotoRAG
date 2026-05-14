"""
TDD tests for the _read_model_config_from_db() helper present in every queue file,
and for the fallback behaviour of _get_model_name() when the DB is unavailable.

Each queue file exposes:
  _read_model_config_from_db(db_path, model_type) -> dict | None
  _get_model_name(db_path, model_type, default) -> str

We test the shared logic independently by importing from src.queues.queue_config
(a new shared module that every queue file will import from).
"""
import sqlite3
import pytest

from src.queues.queue_config import read_model_config_from_db, get_model_name_from_db


# ---------------------------------------------------------------------------
# Fixture: tiny SQLite DB with ai_model_configs table
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_with_clip(tmp_path) -> str:
    db_path = str(tmp_path / "test_main.db")
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE ai_model_configs (
            id INTEGER PRIMARY KEY,
            type TEXT UNIQUE,
            mode TEXT,
            model_name TEXT,
            url TEXT,
            api_key TEXT
        )
    """)
    conn.execute(
        "INSERT INTO ai_model_configs (type, mode, model_name) VALUES (?,?,?)",
        ("clip", "local", "ViT-L-14"),
    )
    conn.execute(
        "INSERT INTO ai_model_configs (type, mode, model_name) VALUES (?,?,?)",
        ("vision", "remote", "gpt-4o"),
    )
    conn.commit()
    conn.close()
    return db_path


# ---------------------------------------------------------------------------
# read_model_config_from_db
# ---------------------------------------------------------------------------

def test_reads_existing_clip_row(db_with_clip):
    cfg = read_model_config_from_db(db_with_clip, "clip")
    assert cfg == {"model_name": "ViT-L-14", "mode": "local"}


def test_reads_existing_vision_row(db_with_clip):
    cfg = read_model_config_from_db(db_with_clip, "vision")
    assert cfg == {"model_name": "gpt-4o", "mode": "remote"}


def test_returns_none_when_type_not_in_table(db_with_clip):
    cfg = read_model_config_from_db(db_with_clip, "embedding")
    assert cfg is None


def test_returns_none_when_db_file_does_not_exist(tmp_path):
    missing = str(tmp_path / "no_such_file.db")
    cfg = read_model_config_from_db(missing, "clip")
    assert cfg is None


def test_returns_none_when_table_missing(tmp_path):
    db_path = str(tmp_path / "empty.db")
    conn = sqlite3.connect(db_path)
    conn.close()  # creates empty DB with no tables
    cfg = read_model_config_from_db(db_path, "clip")
    assert cfg is None


# ---------------------------------------------------------------------------
# get_model_name_from_db (with fallback)
# ---------------------------------------------------------------------------

def test_returns_db_model_name_when_available(db_with_clip):
    name = get_model_name_from_db(db_with_clip, "clip", default="ViT-B-32")
    assert name == "ViT-L-14"


def test_returns_default_when_db_unavailable(tmp_path):
    missing = str(tmp_path / "no_db.db")
    name = get_model_name_from_db(missing, "clip", default="ViT-B-32")
    assert name == "ViT-B-32"


def test_returns_default_when_type_not_found(db_with_clip):
    name = get_model_name_from_db(db_with_clip, "ocr", default="easyocr")
    assert name == "easyocr"


def test_returns_db_mode_when_available(db_with_clip):
    cfg = read_model_config_from_db(db_with_clip, "vision")
    assert cfg["mode"] == "remote"
