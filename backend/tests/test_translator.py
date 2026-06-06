"""
TDD tests for translator.py — language-agnostic direction logic.
Phase 8.1 of multilingual support.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

# Mock heavy ML dependencies before any src.ai.translator import
_mock_torch = MagicMock()
_mock_torch.cuda.is_available.return_value = False
_mock_torch.backends.mps.is_available.return_value = False
sys.modules.setdefault("torch", _mock_torch)
sys.modules.setdefault("transformers", MagicMock())

# Other test files (api/tool) set src.ai and src.ai.translator to MagicMocks.
# Evict them so we import the real translator module (with mocked torch/transformers).
sys.modules.pop("src.ai", None)
sys.modules.pop("src.ai.translator", None)


# ---------------------------------------------------------------------------
# LANG_DICT completeness
# ---------------------------------------------------------------------------


class TestLangDict:
    def test_has_english(self):
        from src.ai.translator import Translator

        assert Translator.LANG_DICT.get("en") == "eng_Latn"

    def test_has_russian(self):
        from src.ai.translator import Translator

        assert Translator.LANG_DICT.get("ru") == "rus_Cyrl"

    def test_has_spanish(self):
        from src.ai.translator import Translator

        assert Translator.LANG_DICT.get("es") == "spa_Latn"


# ---------------------------------------------------------------------------
# Fixture: Translator with mocked model & tokenizer (no GPU, no HuggingFace)
# ---------------------------------------------------------------------------


@pytest.fixture
def translator():
    with patch("src.ai.translator.AutoModelForSeq2SeqLM"), patch("src.ai.translator.AutoTokenizer") as mock_tok_cls:
        mock_tokenizer = MagicMock()
        mock_tokenizer.convert_tokens_to_ids.return_value = 42
        mock_tok_cls.from_pretrained.return_value = mock_tokenizer

        from src.ai.translator import Translator

        t = Translator()
        t.model = MagicMock()
        t.model.generate.return_value = [[1, 2, 3]]
        t.tokenizer = mock_tokenizer
        t.tokenizer.decode.return_value = "translated"
        return t


# ---------------------------------------------------------------------------
# Forward translation (non-English target)
# ---------------------------------------------------------------------------


class TestForwardTranslation:
    def test_forward_to_russian_uses_correct_pair(self, translator):
        translator.translate("Hello", backward=False, target_lang="ru")
        assert translator.tokenizer.src_lang == "eng_Latn"
        assert translator.tokenizer.tgt_lang == "rus_Cyrl"

    def test_forward_to_spanish_uses_correct_pair(self, translator):
        translator.translate("Hello", backward=False, target_lang="es")
        assert translator.tokenizer.src_lang == "eng_Latn"
        assert translator.tokenizer.tgt_lang == "spa_Latn"

    def test_unknown_target_lang_returns_text_unchanged(self, translator):
        result = translator.translate("Hello", backward=False, target_lang="zh")
        assert result == "Hello"
        translator.model.generate.assert_not_called()

    def test_none_target_lang_returns_text_unchanged(self, translator):
        result = translator.translate("Hello", backward=False, target_lang=None)
        assert result == "Hello"
        translator.model.generate.assert_not_called()


# ---------------------------------------------------------------------------
# Backward translation (always → English, used for embedding/search)
# ---------------------------------------------------------------------------


class TestBackwardTranslation:
    def test_backward_from_russian_targets_english(self, translator):
        translator.translate("Привет", backward=True, target_lang="ru")
        assert translator.tokenizer.tgt_lang == "eng_Latn"
        assert translator.tokenizer.src_lang == "rus_Cyrl"

    def test_backward_from_spanish_targets_english(self, translator):
        translator.translate("Hola", backward=True, target_lang="es")
        assert translator.tokenizer.tgt_lang == "eng_Latn"
        assert translator.tokenizer.src_lang == "spa_Latn"

    def test_backward_without_target_lang_still_targets_english(self, translator):
        translator.translate("text", backward=True, target_lang=None)
        assert translator.tokenizer.tgt_lang == "eng_Latn"

    def test_backward_returns_decoded_string(self, translator):
        result = translator.translate("Привет", backward=True, target_lang="ru")
        assert result == "translated"


# ---------------------------------------------------------------------------
# Constructor: no dependency on DEFAULT_LANGUAGE
# ---------------------------------------------------------------------------


class TestConstructor:
    def test_no_hardcoded_direction_dicts(self):
        with patch("src.ai.translator.AutoModelForSeq2SeqLM"), patch("src.ai.translator.AutoTokenizer"):
            from src.ai.translator import Translator

            t = Translator()
        assert not getattr(t, "translate_default_direction", None)
        assert not getattr(t, "translate_default_backward_direction", None)

    def test_constructor_does_not_raise_for_any_default_language(self):
        with (
            patch("src.ai.translator.AutoModelForSeq2SeqLM"),
            patch("src.ai.translator.AutoTokenizer"),
            patch.dict("os.environ", {"DEFAULT_LANGUAGE": "es"}),
        ):
            from src.ai.translator import Translator

            Translator()  # must not raise


# ---------------------------------------------------------------------------
# Supported languages includes Spanish
# ---------------------------------------------------------------------------


class TestSupportedLanguages:
    def test_get_supported_languages_includes_spanish(self):
        with patch("src.ai.translator.AutoModelForSeq2SeqLM"), patch("src.ai.translator.AutoTokenizer"):
            from src.ai.translator import Translator

            t = Translator()
        langs = t.get_supported_languages()
        assert "es" in langs
        assert langs["es"]["lang_code"] == "spa_Latn"
