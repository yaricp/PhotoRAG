import json
import sqlite3
import os
from pathlib import Path

_PROMPTS_JSON_PATH = Path(__file__).parent.parent.parent / "prompts" / "prompts.json"


def load_prompts() -> dict:
    with open(_PROMPTS_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

# Kept for seeding / backward-compat during migration; call sites should use get_prompt() instead.
PROMPTS = load_prompts()


def _get_default_db_path() -> str:
    from src.config import Database_Settings
    return Database_Settings().DATABASE_PATH


def get_prompt(key: str, db_path: str | None = None) -> str:
    """
    Fetch prompt text from the prompts table. No caching — every call hits sqlite3.

    Falls back to prompts.json if:
      - the DB file does not exist yet (first-run / tests)
      - the key row is missing from the DB

    Raises KeyError if the key is not found in the DB or the JSON fallback.
    """
    resolved = db_path if db_path is not None else _get_default_db_path()
    if os.path.exists(resolved):
        try:
            con = sqlite3.connect(resolved)
            row = con.execute(
                "SELECT text FROM prompts WHERE key=?", (key,)
            ).fetchone()
            con.close()
            if row is not None:
                return row[0]
        except Exception:
            pass  # fall through to JSON

    # JSON fallback
    raw = load_prompts()
    parts = key.split(".", 1)
    if len(parts) == 2:
        group, name = parts
        if group in raw and name in raw[group]:
            return raw[group][name]
    raise KeyError(f"Prompt key {key!r} not found in DB or prompts.json")


def expand_tags(tags):
    if not tags:
        return ""

    tag_list = [tag.name for tag in tags]
    return ", ".join(tag_list)


def build_photo_text_for_embedding(
    description: str, tags:list[str], categories:list[str], location: str
) -> str:
    parts = []

    if description:
        parts.append(f"A detailed photo of {description}")

    if tags:
        tags_str = ", ".join(tags)
        parts.append(f"It contains: {tags_str}")

    if categories:
        categories_str = ", ".join(categories)
        parts.append(f"This is related to {categories_str}")

    if location and location != "Unknown Location":
        parts.append(f"Taken at {location}")

    return ". ".join(parts)