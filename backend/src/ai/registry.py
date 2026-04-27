import threading
from src.ai.clip import ClipTagger
from src.ai.vision import QwenVisionGenerator
from src.geo import GeoEnricher
from src.config import Settings
from loguru import logger


class AIModelRegistry:
    """
    Thread-safe Singleton Registry — RAM concern only.
    Loads already-downloaded models into memory once per process.
    Never downloads, never checks the network.
    """
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self._clip_tagger = None
        self._vision_generator = None
        self._nomic_embedder = None
        self._geo_enricher = None
        self.__settings = None  # lazy

    @property
    def _settings(self):
        if self.__settings is None:
            from src.config import Settings
            self.__settings = Settings()
        return self.__settings

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @property
    def clip_tagger(self):
        if self._clip_tagger is None:
            with self._lock:
                if self._clip_tagger is None:
                    logger.info("Registry: Warming up CLIP Tagger...")
                    tagger = ClipTagger()
                    tagger.load()  # assumes download_models_task already ran
                    self._clip_tagger = tagger
        logger.info("Registry: CLIP Tagger is ready.")
        return self._clip_tagger

    @property
    def vision_generator(self):
        if self._vision_generator is None:
            with self._lock:
                if self._vision_generator is None:
                    logger.info("Registry: Warming up Qwen-VL Vision Generator...")
                    generator = QwenVisionGenerator(self._settings)
                    self._vision_generator = generator
        logger.info("Registry: Qwen-VL Vision Generator is ready.")
        return self._vision_generator

    @property
    def nomic_embedder(self):
        if self._nomic_embedder is None:
            with self._lock:
                if self._nomic_embedder is None:
                    logger.info("Registry: Warming up Nomic Semantic Embedder...")
                    from sentence_transformers import SentenceTransformer
                    model = SentenceTransformer('nomic-ai/nomic-embed-text-v1.5', trust_remote_code=True)
                    self._nomic_embedder = model
        logger.info("Registry: Nomic Semantic Embedder is ready.")
        return self._nomic_embedder

    @property
    def geo_enricher(self):
        if self._geo_enricher is None:
            with self._lock:
                if self._geo_enricher is None:
                    self._geo_enricher = GeoEnricher()
        logger.info("Registry: Geo enricher is ready.")
        return self._geo_enricher

# Global Access Point
registry = AIModelRegistry.get_instance()
