from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger


class RemoteTranslator:
    """
    Translate text using a remote provider.

    Supported providers (via `provider` kwarg):
      - "deepl"          → DeepL REST API
      - "libretranslate" → LibreTranslate REST API
      - anything else    → LangChain chat model (openai, anthropic, google_genai, ollama…)
        Pass `llm` directly when using LangChain providers.
    """

    _TRANSLATION_SYSTEM = (
        "You are a professional translator. "
        "Return ONLY the translated text with no explanation, no quotes, and no commentary."
    )
    _TRANSLATION_USER = "Translate the following text to {target_lang}:\n\n{text}"

    def __init__(
        self,
        llm=None,
        provider: str | None = None,
        api_key: str | None = None,
        api_url: str | None = None,
        src_lang: str = "English",
        tgt_lang: str = "Russian",
    ):
        self.llm = llm
        self.provider = (provider or "").lower()
        self.api_key = api_key
        self.api_url = api_url
        self.src_lang = src_lang
        self.tgt_lang = tgt_lang

    def translate(self, text: str, backward: bool = False) -> str:
        target = self.src_lang if backward else self.tgt_lang

        if self.provider == "deepl":
            return self._translate_deepl(text, target)
        if self.provider == "libretranslate":
            return self._translate_libretranslate(text, target)
        return self._translate_llm(text, target)

    # ------------------------------------------------------------------
    # LangChain path
    # ------------------------------------------------------------------

    def _translate_llm(self, text: str, target_lang: str) -> str:
        if self.llm is None:
            raise RuntimeError("RemoteTranslator: no LLM provided for LangChain translation path")
        messages = [
            SystemMessage(content=self._TRANSLATION_SYSTEM),
            HumanMessage(content=self._TRANSLATION_USER.format(target_lang=target_lang, text=text)),
        ]
        try:
            response = self.llm.invoke(messages)
            return response.content.strip()
        except Exception as exc:
            logger.error(f"[RemoteTranslator] LLM call failed: {exc}")
            return text

    # ------------------------------------------------------------------
    # DeepL path
    # ------------------------------------------------------------------

    def _translate_deepl(self, text: str, target_lang: str) -> str:
        import requests

        _LANG_MAP = {
            "English": "EN-US",
            "Russian": "RU",
            "German": "DE",
            "French": "FR",
            "Spanish": "ES",
            "Italian": "IT",
            "Dutch": "NL",
            "Polish": "PL",
            "Portuguese": "PT-BR",
        }
        tgt = _LANG_MAP.get(target_lang, target_lang.upper()[:2])
        base = self.api_url or "https://api-free.deepl.com"
        url = f"{base.rstrip('/')}/v2/translate"
        try:
            resp = requests.post(
                url,
                data={"text": text, "target_lang": tgt},
                headers={"Authorization": f"DeepL-Auth-Key {self.api_key}"},
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()["translations"][0]["text"]
        except Exception as exc:
            logger.error(f"[RemoteTranslator] DeepL call failed: {exc}")
            return text

    # ------------------------------------------------------------------
    # LibreTranslate path
    # ------------------------------------------------------------------

    def _translate_libretranslate(self, text: str, target_lang: str) -> str:
        import requests

        _LANG_MAP = {
            "English": "en",
            "Russian": "ru",
            "German": "de",
            "French": "fr",
            "Spanish": "es",
            "Italian": "it",
        }
        tgt = _LANG_MAP.get(target_lang, target_lang.lower()[:2])
        url = f"{(self.api_url or 'http://localhost:5000').rstrip('/')}/translate"
        payload: dict = {"q": text, "source": "auto", "target": tgt, "format": "text"}
        if self.api_key:
            payload["api_key"] = self.api_key
        try:
            resp = requests.post(url, json=payload, timeout=30)
            resp.raise_for_status()
            return resp.json()["translatedText"]
        except Exception as exc:
            logger.error(f"[RemoteTranslator] LibreTranslate call failed: {exc}")
            return text
