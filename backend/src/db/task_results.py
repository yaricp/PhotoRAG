import json
import sqlite3
from loguru import logger
from src.config import Database_Settings


settings = Database_Settings()
RESULTS_DB = settings.TASK_RESULTS_DATABASE_NAME

_ERROR_KEY = "__error__"


def init_db() -> None:
    conn = sqlite3.connect(RESULTS_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS results (
            task_id    TEXT PRIMARY KEY,
            result     TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


# Ensure the table exists the moment this module is imported by any queue worker.
init_db()


def save_result(task_id: str, result: str) -> None:
    """Store a successful result string (typically JSON-encoded)."""
    conn = sqlite3.connect(RESULTS_DB)
    conn.execute(
        "INSERT OR REPLACE INTO results (task_id, result) VALUES (?, ?)",
        (task_id, result)
    )
    conn.commit()
    conn.close()
    logger.debug(f"[task_results] Result saved for task_id={task_id} with result length {len(result)}")


def save_error(task_id: str, error: str) -> None:
    """Store a failure marker. get_result() will raise RuntimeError for this task_id."""
    payload = json.dumps({_ERROR_KEY: error})
    conn = sqlite3.connect(RESULTS_DB)
    conn.execute(
        "INSERT OR REPLACE INTO results (task_id, result) VALUES (?, ?)",
        (task_id, payload)
    )
    conn.commit()
    conn.close()
    logger.debug(f"[task_results] Error saved for task_id={task_id} with error length {len(error)}")

def get_result(task_id: str) -> str | None:
    """
    Return the raw result string, or None if not yet available.
    Raises RuntimeError if the result was stored via save_error().
    """
    conn = sqlite3.connect(RESULTS_DB)
    row = conn.execute(
        "SELECT result FROM results WHERE task_id = ?",
        (task_id,)
    ).fetchone()
    conn.close()

    if row is None:
        return None

    raw = row[0]
    # Check if this is an error marker
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict) and _ERROR_KEY in parsed:
            raise RuntimeError(parsed[_ERROR_KEY])
    except (json.JSONDecodeError, TypeError):
        pass  # not JSON — treat as a plain string result

    return raw


def cleanup_old_results(max_age_seconds: float = 3600) -> int:
    """
    Delete results older than max_age_seconds.
    Returns the number of rows deleted.
    """
    conn = sqlite3.connect(RESULTS_DB)
    cursor = conn.execute(
        "DELETE FROM results WHERE created_at < datetime('now', ? || ' seconds')",
        (f"-{int(max_age_seconds)}",)
    )
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted
