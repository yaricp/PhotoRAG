import threading
from loguru import logger
from src.config import ML_Settings


class AIModelRegistry:
    """
    Thread-safe Singleton Registry — RAM concern only.
    Loads already-downloaded models into memory once per process.
    Respects local/remote mode from ML_Settings.
    Never downloads, never checks the network.
    """
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self._clip_tagger = None
        self._vision_generator = None
        self._nomic_embedder = None
        self._geo_enricher = None
        self._settings = None

        self._clip_lock = threading.Lock()
        self._vision_lock = threading.Lock()
        self._nomic_lock = threading.Lock()
        self._nomic_inference_lock = threading.Lock()
        self._geo_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "AIModelRegistry":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @property
    def settings(self) -> ML_Settings:
        if self._settings is None:
            self._settings = ML_Settings()
        return self._settings

    # ------------------------------------------------------------------
    # CLIP — всегда local
    # ------------------------------------------------------------------

    @property
    def clip_tagger(self):
        if self._clip_tagger is None:
            with self._clip_lock:
                if self._clip_tagger is None:
                    logger.info("[registry] Warming up CLIP Tagger...")
                    from src.ai.clip import ClipTagger
                    tagger = ClipTagger()
                    tagger.load_model()
                    tagger.load_tags()               # загрузить tags.npy в память
                    tagger.load_or_compute_categories()  # загрузить categories.npy
                    self._clip_tagger = tagger
                    logger.info("[registry] CLIP Tagger ready ✓")
        return self._clip_tagger

    # ------------------------------------------------------------------
    # Vision — local или remote
    # ------------------------------------------------------------------

    @property
    def vision_generator(self):
        if self._vision_generator is None:
            with self._vision_lock:
                if self._vision_generator is None:
                    if self.settings.VISION_MODE == "local":
                        logger.info("[registry] Warming up Qwen-VL Vision Generator...")
                        from src.ai.vision import QwenVisionGenerator
                        self._vision_generator = QwenVisionGenerator()
                        logger.info("[registry] Qwen-VL Vision Generator ready ✓")
                    else:
                        logger.info("[registry] Vision mode=remote, using API client.")
                        from src.ai.vision_remote import RemoteVisionGenerator
                        self._vision_generator = RemoteVisionGenerator()
        return self._vision_generator

    def generate_vision_text(self, file_path: str, prompt_key: str) -> str:
        """Единая точка входа — local или remote прозрачно для tasks.py"""
        return self.vision_generator.generate_vision_text(
            file_path=file_path,
            prompt_key=prompt_key,
        )

    # ------------------------------------------------------------------
    # Embedding — local или remote
    # ------------------------------------------------------------------

    @property
    def nomic_embedder(self):
        if self._nomic_embedder is None:
            with self._nomic_lock:
                if self._nomic_embedder is None:
                    if self.settings.EMBEDDING_MODE == "local":
                        logger.info("[registry] Warming up Nomic Embedder...")
                        from sentence_transformers import SentenceTransformer
                        model = SentenceTransformer(
                            self.settings.PHOTO_EMBEDDER_MODEL,
                            trust_remote_code=True,
                        )
                        model.max_seq_length = 512
                        model.name = self.settings.PHOTO_EMBEDDER_MODEL
                        self._nomic_embedder = model
                        logger.info("[registry] Nomic Embedder ready ✓")
                    else:
                        logger.info("[registry] Embedding mode=remote, using API client.")
                        from src.ai.embedding_remote import RemoteEmbedder
                        self._nomic_embedder = RemoteEmbedder()
        return self._nomic_embedder

    def embedder_encode_text(self, text: str, purpose: str = "save") -> list:
        """Единая точка входа — local или remote прозрачно для tasks.py"""
        if self.settings.EMBEDDING_MODE == "local":
            if purpose == "search":
                text = f"search_query: {text}"
            elif purpose == "save":
                text = f"search_document: {text}"
            with self._nomic_inference_lock:
                return self.nomic_embedder.encode(text, normalize_embeddings=True)
        else:
            return self.nomic_embedder.encode(text, purpose=purpose)

    # ------------------------------------------------------------------
    # Geo — всегда local (lightweight, no GPU)
    # ------------------------------------------------------------------

    @property
    def geo_enricher(self):
        if self._geo_enricher is None:
            with self._geo_lock:
                if self._geo_enricher is None:
                    from src.geo import GeoEnricher
                    self._geo_enricher = GeoEnricher()
                    logger.info("[registry] Geo Enricher ready ✓")
        return self._geo_enricher


# Global access point
registry = AIModelRegistry.get_instance()
