"""
TDD tests for the installer bootstrap reader — Phase 8.9.

The NSIS installer writes %APPDATA%\\PhotoRAG\bootstrap.json so the backend
reads it on first startup and applies the selected language without a
second Settings-page visit.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch


def _run(tmp_path: Path, content: dict | None, existing_lang: str | None = None):
    """Write bootstrap.json if content given, call apply_bootstrap_settings, return mocks."""
    from src.bootstrap import apply_bootstrap_settings

    bootstrap_path = tmp_path / "bootstrap.json"
    if content is not None:
        bootstrap_path.write_text(json.dumps(content))

    db = MagicMock()

    with (
        patch("src.bootstrap._bootstrap_path", return_value=bootstrap_path),
        patch("src.bootstrap.get_setting", return_value=existing_lang),
        patch("src.bootstrap.set_setting") as mock_set,
    ):
        apply_bootstrap_settings(db)

    return mock_set, bootstrap_path


class TestApplyBootstrapSettings:
    def test_applies_language_when_not_yet_set(self, tmp_path):
        mock_set, _ = _run(tmp_path, {"default_language": "ru"}, existing_lang=None)
        mock_set.assert_called_once()
        assert mock_set.call_args[0][2] == "ru"

    def test_applies_spanish(self, tmp_path):
        mock_set, _ = _run(tmp_path, {"default_language": "es"}, existing_lang=None)
        assert mock_set.call_args[0][2] == "es"

    def test_skips_when_language_already_set(self, tmp_path):
        mock_set, _ = _run(tmp_path, {"default_language": "ru"}, existing_lang="en")
        mock_set.assert_not_called()

    def test_file_deleted_after_applying(self, tmp_path):
        _, path = _run(tmp_path, {"default_language": "ru"}, existing_lang=None)
        assert not path.exists()

    def test_file_not_deleted_when_skipped(self, tmp_path):
        _, path = _run(tmp_path, {"default_language": "ru"}, existing_lang="en")
        assert path.exists()

    def test_no_op_when_file_missing(self, tmp_path):
        mock_set, _ = _run(tmp_path, content=None, existing_lang=None)
        mock_set.assert_not_called()

    def test_no_op_on_malformed_json(self, tmp_path):
        from src.bootstrap import apply_bootstrap_settings

        bootstrap_path = tmp_path / "bootstrap.json"
        bootstrap_path.write_text("not valid json {{{{")
        db = MagicMock()

        with (
            patch("src.bootstrap._bootstrap_path", return_value=bootstrap_path),
            patch("src.bootstrap.get_setting", return_value=None),
            patch("src.bootstrap.set_setting") as mock_set,
        ):
            apply_bootstrap_settings(db)  # must not raise

        mock_set.assert_not_called()

    def test_defaults_to_english_when_key_missing(self, tmp_path):
        mock_set, _ = _run(tmp_path, {"some_other_key": "value"}, existing_lang=None)
        mock_set.assert_called_once()
        assert mock_set.call_args[0][2] == "en"
