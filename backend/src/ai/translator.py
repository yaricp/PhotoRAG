import torch
from loguru import logger
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

from src.config import Translation_Settings as ML_Settings


class Translator:
    ml_settings = ML_Settings()
    MODEL_ID = ml_settings.TRANSLATOR_MODEL

    LANG_DICT = {
        "en": "eng_Latn",
        "ru": "rus_Cyrl",
        "es": "spa_Latn",
    }

    def __init__(self):
        self.model = None
        self.tokenizer = None

        if torch.cuda.is_available():
            self.device = "cuda"
        elif torch.backends.mps.is_available():
            self.device = "mps"
        else:
            self.device = "cpu"

    def download(self):
        """Pre-downloads the models and weights from HuggingFace."""
        AutoModelForSeq2SeqLM.from_pretrained(self.MODEL_ID)
        AutoTokenizer.from_pretrained(self.MODEL_ID)

    def load(self):
        if not self.model:
            logger.info(f"Translator: Loading {self.MODEL_ID} on {self.device}...")
            self.model = AutoModelForSeq2SeqLM.from_pretrained(self.MODEL_ID).to(self.device)
            self.tokenizer = AutoTokenizer.from_pretrained(self.MODEL_ID)
            self.model.eval()
            logger.info(f"Translator: {self.MODEL_ID} loaded on {self.device}")

    def translate(self, text: str, backward: bool = False, target_lang: str | None = None) -> str:
        """
        Translate text.

        backward=False: English → target_lang (for displaying descriptions).
                        Returns text unchanged if target_lang is unknown or None.
        backward=True:  user language → English (for embedding/search queries).
                        target_lang specifies the source language; defaults to "ru" if omitted.
        """
        if backward:
            # Always translate → English; source = user's current language
            src_code = self.LANG_DICT.get(target_lang, "rus_Cyrl") if target_lang else "rus_Cyrl"
            self.load()
            self.tokenizer.src_lang = src_code
            self.tokenizer.tgt_lang = "eng_Latn"
        elif target_lang and target_lang in self.LANG_DICT:
            # Descriptions are always generated in English
            self.load()
            self.tokenizer.src_lang = "eng_Latn"
            self.tokenizer.tgt_lang = self.LANG_DICT[target_lang]
        else:
            logger.warning(
                f"Translator.translate: unknown or missing target_lang={target_lang!r}, returning text unchanged"
            )
            return text

        logger.debug(f"Translator: {self.tokenizer.src_lang} -> {self.tokenizer.tgt_lang} | {text}")
        inputs = self.tokenizer(text, return_tensors="pt").to(self.device)
        target_lang_id = self.tokenizer.convert_tokens_to_ids(self.tokenizer.tgt_lang)
        outputs = self.model.generate(**inputs, forced_bos_token_id=target_lang_id)
        result = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        logger.debug(f"Translator result: {result}")
        return result

    def _build_supported_languages_from_model(self):
        self.supported_languages = {
            code: {"lang_code": nllb_code, "lang_name": self._lang_name(code)}
            for code, nllb_code in self.LANG_DICT.items()
            if code != "en"
        }

    @staticmethod
    def _lang_name(code: str) -> str:
        return {"ru": "Russian", "es": "Spanish"}.get(code, code.upper())

    def get_supported_languages(self):
        """Returns the list of supported languages."""
        if not getattr(self, "supported_languages", None):
            self._build_supported_languages_from_model()
        return self.supported_languages
