"""
TDD tests for src/db/task_results.py

Covers:
- save_result / get_result roundtrip
- save_error / get_result raises RuntimeError
- concurrent writers (threading)
- cleanup_old_results removes stale rows
- get_result returns None when no row exists
"""

import json
import sqlite3
import threading
import time

import pytest

from src.db.task_results import (
    cleanup_old_results,
    get_result,
    init_db,
    save_error,
    save_result,
)

# ---------------------------------------------------------------------------
# Fixture: isolated in-memory DB for every test
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Point RESULTS_DB at a fresh temp file for every test."""
    db_file = str(tmp_path / "task_results_test.db")
    monkeypatch.setattr("src.db.task_results.RESULTS_DB", db_file)
    init_db()
    yield db_file


# ---------------------------------------------------------------------------
# Basic roundtrip
# ---------------------------------------------------------------------------


def test_save_and_get_string():
    save_result("t1", "hello")
    assert get_result("t1") == "hello"


def test_save_and_get_json_dict():
    payload = json.dumps({"key": [1, 2, 3], "nested": {"a": True}})
    save_result("t2", payload)
    assert json.loads(get_result("t2")) == {"key": [1, 2, 3], "nested": {"a": True}}


def test_save_and_get_json_list():
    payload = json.dumps([["tag", 0.9], ["cat", 0.7]])
    save_result("t3", payload)
    assert json.loads(get_result("t3")) == [["tag", 0.9], ["cat", 0.7]]


def test_get_result_returns_none_when_absent():
    assert get_result("nonexistent-id") is None


# ---------------------------------------------------------------------------
# save_error + get_result
# ---------------------------------------------------------------------------


def test_save_error_makes_get_result_raise():
    """save_error should store an error marker; get_result should raise RuntimeError."""
    save_error("e1", "something exploded")
    with pytest.raises(RuntimeError, match="something exploded"):
        get_result("e1")


def test_save_error_does_not_conflict_with_normal_result():
    save_result("ok1", "fine")
    save_error("err1", "bad")
    assert get_result("ok1") == "fine"
    with pytest.raises(RuntimeError):
        get_result("err1")


# ---------------------------------------------------------------------------
# Concurrent writers
# ---------------------------------------------------------------------------


def test_concurrent_writers():
    """10 threads each save their own task_id; all must be retrievable."""
    n = 10
    ids = [f"concurrent-{i}" for i in range(n)]
    errors = []

    def writer(task_id):
        try:
            save_result(task_id, json.dumps({"id": task_id}))
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(tid,)) for tid in ids]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Writers raised: {errors}"
    for tid in ids:
        raw = get_result(tid)
        assert json.loads(raw) == {"id": tid}


def test_concurrent_save_and_get():
    """Writer thread sleeps briefly then saves; reader polls until result appears."""
    task_id = "race-condition"
    result_holder = []

    def writer():
        time.sleep(0.1)
        save_result(task_id, "arrived")

    t = threading.Thread(target=writer)
    t.start()

    # Poll up to 1 s
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        val = get_result(task_id)
        if val is not None:
            result_holder.append(val)
            break
        time.sleep(0.02)

    t.join()
    assert result_holder == ["arrived"]


# ---------------------------------------------------------------------------
# cleanup_old_results
# ---------------------------------------------------------------------------


def test_cleanup_removes_old_rows(isolated_db):
    """Rows older than max_age_seconds should be deleted; newer ones kept."""
    save_result("old-1", "stale")
    save_result("old-2", "stale")
    save_result("fresh", "keep me")

    # Back-date the two old rows directly in sqlite
    conn = sqlite3.connect(isolated_db)
    conn.execute("UPDATE results SET created_at = datetime('now', '-2 hours') WHERE task_id IN ('old-1','old-2')")
    conn.commit()
    conn.close()

    deleted = cleanup_old_results(max_age_seconds=3600)  # 1 hour threshold

    assert deleted == 2
    assert get_result("old-1") is None
    assert get_result("old-2") is None
    assert get_result("fresh") == "keep me"


def test_cleanup_returns_zero_when_nothing_old():
    save_result("new-row", "value")
    deleted = cleanup_old_results(max_age_seconds=3600)
    assert deleted == 0


def test_cleanup_removes_nothing_when_table_empty():
    deleted = cleanup_old_results(max_age_seconds=60)
    assert deleted == 0
