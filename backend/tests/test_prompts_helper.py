"""
Tests for get_prompt() — the no-cache DB-backed prompt fetcher.
Written before implementation (TDD).
"""
import pytest
import tempfile
import os
import sqlite3
from pathlib import Path
from unittest.mock import patch


PROMPTS_JSON = Path(__file__).parent.parent / "prompts" / "prompts.json"


@pytest.fixture()
def populated_db(tmp_path):
    """Create a temp SQLite DB with the prompts table populated."""
    db_file = str(tmp_path / "test.db")
    con = sqlite3.connect(db_file)
    con.execute("""
        CREATE TABLE prompts (
            id INTEGER PRIMARY KEY,
            key TEXT UNIQUE NOT NULL,
            "group" TEXT NOT NULL,
            name TEXT NOT NULL,
            title TEXT NOT NULL,
            text TEXT NOT NULL,
            description TEXT,
            updated_at TEXT
        )
    """)
    con.execute(
        "INSERT INTO prompts (key, \"group\", name, title, text) VALUES (?, ?, ?, ?, ?)",
        ("vision_analysis.describe_scene", "vision_analysis", "describe_scene", "Test title", "My describe prompt"),
    )
    con.execute(
        "INSERT INTO prompts (key, \"group\", name, title, text) VALUES (?, ?, ?, ?, ?)",
        ("chat_agent.system_message", "chat_agent", "system_message", "Chat system", "My system message"),
    )
    con.commit()
    con.close()
    return db_file


class TestGetPrompt:
    def test_reads_from_db(self, populated_db):
        from src.ai.prompts import get_prompt
        text = get_prompt("vision_analysis.describe_scene", db_path=populated_db)
        assert text == "My describe prompt"

    def test_reads_different_key(self, populated_db):
        from src.ai.prompts import get_prompt
        text = get_prompt("chat_agent.system_message", db_path=populated_db)
        assert text == "My system message"

    def test_falls_back_to_json_when_key_missing_in_db(self, populated_db):
        """Key exists in JSON but not in DB — fall back to JSON value."""
        import json
        from src.ai.prompts import get_prompt
        raw = json.loads(PROMPTS_JSON.read_text())
        expected = raw["vision_analysis"]["system_prompt"]
        text = get_prompt("vision_analysis.system_prompt", db_path=populated_db)
        assert text == expected

    def test_falls_back_to_json_when_db_missing(self, tmp_path):
        """DB file does not exist — fall back to JSON."""
        import json
        from src.ai.prompts import get_prompt
        missing_db = str(tmp_path / "nonexistent.db")
        raw = json.loads(PROMPTS_JSON.read_text())
        expected = raw["vision_analysis"]["describe_scene"]
        text = get_prompt("vision_analysis.describe_scene", db_path=missing_db)
        assert text == expected

    def test_raises_for_completely_unknown_key(self, populated_db):
        """Key not in DB and not in JSON — raises KeyError."""
        from src.ai.prompts import get_prompt
        with pytest.raises(KeyError):
            get_prompt("nonexistent.totally_unknown", db_path=populated_db)

    def test_uses_database_settings_path_by_default(self, populated_db):
        """When db_path is None, uses Database_Settings().DATABASE_PATH."""
        from src.ai.prompts import get_prompt
        with patch("src.ai.prompts._get_default_db_path", return_value=populated_db):
            text = get_prompt("vision_analysis.describe_scene")
            assert text == "My describe prompt"

    def test_reflects_updated_value_immediately(self, populated_db):
        """After updating the DB directly, get_prompt returns new value without restart."""
        from src.ai.prompts import get_prompt
        con = sqlite3.connect(populated_db)
        con.execute("UPDATE prompts SET text=? WHERE key=?", ("Updated!", "vision_analysis.describe_scene"))
        con.commit()
        con.close()
        assert get_prompt("vision_analysis.describe_scene", db_path=populated_db) == "Updated!"
