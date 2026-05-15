import json
import sqlite3
import os
from loguru import logger
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


def normalize_for_embedding(
    raw_description: str,
    categories: list[str],
    location: str | None,
) -> str:
    """
    Clean a raw vision-model description and assemble it with context for embedding.

    Strips common model-generated preamble phrases, removes any residual
    "This is related to…" sentences, then appends category and location.
    """
    import re

    _JUNK_PREFIXES = [
        "a detailed photo of",
        "the photo depicts",
        "this image shows",
        "the image depicts",
        "a photo of",
        "a picture of",
        "in this image,",
        "in this photo,",
        "The photo captures",
        "The image captures",
        
    ]

    text = raw_description.strip() if raw_description else ""
    for prefix in _JUNK_PREFIXES:
        if text.lower().startswith(prefix):
            text = text[len(prefix):].lstrip(", .")
            if text:
                text = text[0].upper() + text[1:]
            break

    text = re.sub(r'\s*This is related to[^.]+\.', '', text).strip()

    parts = [text] if text else []

    if categories:
        cats = ", ".join(c.strip() for c in categories if c.strip())
        if cats:
            parts.append(f"Category: {cats}.")

    if location and location != "Unknown Location":
        parts.append(f"Location: {location}.")

    return " ".join(parts)


def build_photo_text_for_embedding(
    description: str, tags: list[str], categories: list[str], location: str
) -> str:
    text = normalize_for_embedding(description, categories, location)
    logger.debug(f"Normalized description for embedding: {text}")
    if tags:
        tags_str = ", ".join(t.strip() for t in tags if t.strip())
        if tags_str:
            text += f" Tags: {tags_str}."

    return text