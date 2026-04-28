import threading
from src.ai.clip import ClipTagger
from src.ai.vision import QwenVisionGenerator
from src.geo import GeoEnricher
from src.config import ML_Settings
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

        self._clip_lock = threading.Lock()
        self._vision_lock = threading.Lock()
        self._nomic_lock = threading.Lock()
        self._nomic_inference_lock = threading.Lock()
        self._geo_lock = threading.Lock()

    @property
    def _settings(self):
        if self.__settings is None:
            # from src.config import Settings
            self.__settings = ML_Settings()
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
            with self._clip_lock:
                if self._clip_tagger is None:
                    logger.info("Registry: Warming up CLIP Tagger...")
                    tagger = ClipTagger()
                    tagger.load_model()  # assumes download_models_task already ran
                    self._clip_tagger = tagger
        logger.info("Registry: CLIP Tagger is ready.")
        return self._clip_tagger

    @property
    def vision_generator(self):
        if self._vision_generator is None:
            with self._vision_lock:
                if self._vision_generator is None:
                    logger.info("Registry: Warming up Qwen-VL Vision Generator...")
                    generator = QwenVisionGenerator()
                    self._vision_generator = generator
        logger.info("Registry: Qwen-VL Vision Generator is ready.")
        return self._vision_generator

    @property
    def nomic_embedder(self):
        if self._nomic_embedder is None:
            with self._nomic_lock:
                if self._nomic_embedder is None:
                    logger.info("Registry: Warming up Nomic Semantic Embedder...")
                    from sentence_transformers import SentenceTransformer
                    logger.info(f"Loading model: {self._settings.PHOTO_EMBEDDER_MODEL}")
                    model = SentenceTransformer(
                        self._settings.PHOTO_EMBEDDER_MODEL, trust_remote_code=True
                    )
                    model.max_seq_length = 512
                    model.name = self._settings.PHOTO_EMBEDDER_MODEL
                    self._nomic_embedder = model
        logger.info(f"Registry: {self._nomic_embedder.name} is ready.")
        return self._nomic_embedder

    def embedder_encode_text(self, text: str, purpose: str = "save"):
        if purpose == "search":
            text = f"search_query: {text}"
        elif purpose == "save":
            text = f"search_document: {text}"
        with self._nomic_inference_lock:
            return self.nomic_embedder.encode(text)

    @property
    def geo_enricher(self):
        if self._geo_enricher is None:
            with self._geo_lock:
                if self._geo_enricher is None:
                    self._geo_enricher = GeoEnricher()
        logger.info("Registry: Geo enricher is ready.")
        return self._geo_enricher

# Global Access Point
registry = AIModelRegistry.get_instance()
