
from loguru import logger
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
import torch

from src.config import Translation_Settings as ML_Settings, Main_Settings
from src.schemas import TranslateRequest


class Translator:

    ml_settings = ML_Settings()
    MODEL_ID = ml_settings.TRANSLATOR_MODEL
    main_settings = Main_Settings()
    LANG_DICT = {
        "en": "eng_Latn",
        "ru": "rus_Cyrl",
    }

    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.translate_default_direction = {}
        if self.main_settings.DEFAULT_LANGUAGE == "en":
            self.translate_default_direction["src_lang"] = "rus_Cyrl"
            self.translate_default_direction["tgt_lang"] = "eng_Latn"
        elif self.main_settings.DEFAULT_LANGUAGE == "ru":
            self.translate_default_direction["src_lang"] = "eng_Latn"
            self.translate_default_direction["tgt_lang"] = "rus_Cyrl"

        self.translate_default_backward_direction  = {}
        if self.main_settings.DEFAULT_LANGUAGE == "en":
            self.translate_default_backward_direction["src_lang"] = "eng_Latn"
            self.translate_default_backward_direction["tgt_lang"] = "rus_Cyrl"
        elif self.main_settings.DEFAULT_LANGUAGE == "ru":
            self.translate_default_backward_direction["src_lang"] = "rus_Cyrl"
            self.translate_default_backward_direction["tgt_lang"] = "eng_Latn"

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

    def translate(self, text:str, backward: bool = False) -> str:
        self.load()
        if backward:
            self.tokenizer.src_lang = self.translate_default_backward_direction["src_lang"]
            self.tokenizer.tgt_lang = self.translate_default_backward_direction["tgt_lang"]
        else:
            self.tokenizer.src_lang = self.translate_default_direction["src_lang"]
            self.tokenizer.tgt_lang = self.translate_default_direction["tgt_lang"]
        logger.debug(f"Translator: {self.tokenizer.src_lang} -> {self.tokenizer.tgt_lang} | {text}")
        inputs = self.tokenizer(text, return_tensors="pt").to(self.device)
        target_lang_id = self.tokenizer.convert_tokens_to_ids(self.tokenizer.tgt_lang)
        outputs = self.model.generate(**inputs,forced_bos_token_id=target_lang_id)
        result = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        logger.debug(f"Translator result: {result}")
        return result

    def _build_supported_languages_from_model(self):
        self.supported_languages = {
            "en": {
                "lang_code": "eng_Latn",
                "lang_name": "English",
            },
            "ru": {
                "lang_code": "rus_Cyrl",
                "lang_name": "Russian",
            },
        }

    def get_supported_languages(self):
        """Returns the list of supported languages."""
        if not self.supported_languages:
            self._build_supported_languages_from_model()
        return self.supported_languages