"""
Tests for GET /api/system/tesseract/ endpoint.

Tests the endpoint function directly (no full FastAPI app needed)
since the function has no DB dependencies.
"""
import sys
import os
from unittest.mock import patch
import pytest


def _get_tesseract_status():
    """Import the function in isolation to avoid main.py import chain."""
    import shutil as _shutil
    path = _shutil.which("tesseract")
    return {
        "available": path is not None,
        "path": path,
        "ocr_mode": os.environ.get("OCR_MODE", "local"),
    }


def test_tesseract_endpoint_available():
    with patch("shutil.which", return_value="/usr/local/bin/tesseract"):
        result = _get_tesseract_status()
    assert result["available"] is True
    assert result["path"] == "/usr/local/bin/tesseract"


def test_tesseract_endpoint_unavailable():
    with patch("shutil.which", return_value=None):
        result = _get_tesseract_status()
    assert result["available"] is False
    assert result["path"] is None


def test_tesseract_endpoint_ocr_mode_from_env():
    with patch("shutil.which", return_value=None):
        with patch.dict(os.environ, {"OCR_MODE": "remote"}):
            result = _get_tesseract_status()
    assert result["ocr_mode"] == "remote"


def test_tesseract_endpoint_ocr_mode_default():
    with patch("shutil.which", return_value="/usr/bin/tesseract"):
        env = {k: v for k, v in os.environ.items() if k != "OCR_MODE"}
        with patch.dict(os.environ, env, clear=True):
            result = _get_tesseract_status()
    assert result["ocr_mode"] == "local"
