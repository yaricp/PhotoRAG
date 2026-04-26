import threading
from src.ai.clip import ClipTagger
from src.ai.vision import QwenVisionGenerator
from src.config import Settings

class AIModelRegistry:
    """
    Thread-safe Singleton Registry to keep AI models warm in memory.
    Prevents repeated disk I/O and VRAM fragmentation.
    """
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self._clip_tagger = None
        self._vision_generator = None
        self._nomic_embedder = None
        self._settings = Settings()

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
                    print("Registry: Warming up CLIP Tagger...")
                    tagger = ClipTagger()
                    tagger.load() # Force load into memory
                    self._clip_tagger = tagger
        return self._clip_tagger

    @property
    def vision_generator(self):
        if self._vision_generator is None:
            with self._lock:
                if self._vision_generator is None:
                    print("Registry: Warming up Qwen-VL Vision Generator...")
                    generator = QwenVisionGenerator(self._settings)
                    # Qwen loads on first use or explicit call if implemented
                    self._vision_generator = generator
        return self._vision_generator

    @property
    def nomic_embedder(self):
        if self._nomic_embedder is None:
            with self._lock:
                if self._nomic_embedder is None:
                    print("Registry: Warming up Nomic Semantic Embedder...")
                    from sentence_transformers import SentenceTransformer
                    model = SentenceTransformer('nomic-ai/nomic-embed-text-v1.5', trust_remote_code=True)
                    self._nomic_embedder = model
        return self._nomic_embedder

# Global Access Point
registry = AIModelRegistry.get_instance()
