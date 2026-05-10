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


