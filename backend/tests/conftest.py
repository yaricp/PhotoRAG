"""
conftest.py — Global test fixtures and environment setup.

Sets required environment variables BEFORE any module is imported,
preventing pydantic Settings validation errors during test collection.
"""
import os
import sys
import pytest

# Set test env vars before any src.* import touches Settings()
os.environ.setdefault("DATABASE_HOST", "localhost")
os.environ.setdefault("DATABASE_PORT", "5432")
os.environ.setdefault("DATABASE_USER", "test")
os.environ.setdefault("DATABASE_PASSWORD", "test")
os.environ.setdefault("DATABASE_NAME", "test_photo_db")
os.environ.setdefault("VISION_DESCRIBER_MODEL", "Qwen/Qwen2-VL-7B-Instruct")

# Redirect all mutable data paths to a temp dir so tests never touch
# ~/Library/Application Support/PhotoRAG/ or the project root.
import tempfile as _tempfile
_test_data_dir = os.path.join(_tempfile.gettempdir(), "photo_describer_test")
os.makedirs(_test_data_dir, exist_ok=True)
os.environ.setdefault("APP_DATA_DIR", _test_data_dir)
os.environ.setdefault("QUEUE_DB_DIR", _test_data_dir)


