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
        self._translator = None
        self._chat_model = None
        self._settings = None

        self._clip_lock = threading.Lock()
        self._vision_lock = threading.Lock()
        self._nomic_lock = threading.Lock()
        self._nomic_inference_lock = threading.Lock()
        self._geo_lock = threading.Lock()
        self._translator_lock = threading.Lock()
        self._chat_lock = threading.Lock()

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

    def get_model_config(self, model_type: str):
        from src.database import SessionLocal
        from src.db_service import get_model_config as db_get_model_config
        
        db = SessionLocal()
        try:
            return db_get_model_config(db, model_type)
        finally:
            db.close()

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
                    config = self.get_model_config("vision")
                    mode = config.mode if config else self.settings.VISION_MODE
                    
                    if mode == "local":
                        logger.info("[registry] Warming up Qwen-VL Vision Generator...")
                        from src.ai.vision import QwenVisionGenerator
                        self._vision_generator = QwenVisionGenerator()
                        logger.info("[registry] Qwen-VL Vision Generator ready ✓")
                    else:
                        logger.info("[registry] Vision mode=remote, using API client.")
                        from src.ai.vision_remote import RemoteVisionGenerator
                        
                        api_key = config.api_key if config and config.api_key else self.settings.VISION_API_KEY
                        api_url = config.url if config and config.url else self.settings.VISION_API_URL
                        model_name = config.model_name if config and config.model_name else self.settings.VISION_DESCRIBER_MODEL
                        
                        self._vision_generator = RemoteVisionGenerator(
                            api_key=api_key,
                            api_url=api_url,
                            model_name=model_name
                        )
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
                    config = self.get_model_config("embedding")
                    mode = config.mode if config else self.settings.EMBEDDING_MODE
                    
                    if mode == "local":
                        logger.info("[registry] Warming up Nomic Embedder...")
                        model_name = config.model_name if config and config.model_name else self.settings.PHOTO_EMBEDDER_MODEL
                        from sentence_transformers import SentenceTransformer
                        model = SentenceTransformer(
                            model_name,
                            trust_remote_code=True,
                        )
                        model.max_seq_length = 512
                        model.name = model_name
                        self._nomic_embedder = model
                        logger.info("[registry] Nomic Embedder ready ✓")
                    else:
                        logger.info("[registry] Embedding mode=remote, using API client.")
                        from src.ai.embedding_remote import RemoteEmbedder
                        
                        api_key = config.api_key if config and config.api_key else self.settings.EMBEDDING_API_KEY
                        api_url = config.url if config and config.url else self.settings.EMBEDDING_API_URL
                        model_name = config.model_name if config and config.model_name else self.settings.PHOTO_EMBEDDER_MODEL
                        
                        self._nomic_embedder = RemoteEmbedder(
                            api_key=api_key,
                            api_url=api_url,
                            model_name=model_name
                        )
        return self._nomic_embedder

    def embedder_encode_text(self, text: str, purpose: str = "save") -> list:
        """Единая точка входа — local или remote прозрачно для tasks.py"""
        config = self.get_model_config("embedding")
        mode = config.mode if config else self.settings.EMBEDDING_MODE
        
        if mode == "local":
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

    @property
    def translator(self):
        if self._translator is None:
            with self._translator_lock:
                if self._translator is None:
                    from src.ai.translator import Translator
                    self._translator = Translator()
                    logger.info("[registry] Translator ready ✓")
        return self._translator

    @property
    def chat_model(self):
        if self._chat_model is None:
            with self._chat_lock:
                if self._chat_model is None:
                    config = self.get_model_config("chat")
                    mode = config.mode if config else self.settings.CHAT_MODEL_MODE
                    
                    if mode == "local":
                        model_id = config.model_name if config and config.model_name else self.settings.CHAT_LOCAL_MODEL
                        logger.info(f"[registry] Warming up local Chat Model: {model_id}")
                        from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline, BitsAndBytesConfig
                        from langchain_huggingface import HuggingFacePipeline, ChatHuggingFace
                        import torch
                        
                        tokenizer = AutoTokenizer.from_pretrained(model_id)
                        
                        # Use 4-bit quantization if possible to fit larger models and speed up inference
                        bnb_config = BitsAndBytesConfig(
                            load_in_4bit=True,
                            bnb_4bit_compute_dtype=torch.float16,
                            bnb_4bit_quant_type="nf4",
                        )
                        
                        try:
                            model = AutoModelForCausalLM.from_pretrained(
                                model_id,
                                device_map="auto",
                                quantization_config=bnb_config,
                                trust_remote_code=True
                            )
                        except Exception as e:
                            logger.warning(f"[registry] Failed to load with quantization: {e}. Falling back to default.")
                            model = AutoModelForCausalLM.from_pretrained(
                                model_id,
                                device_map="auto",
                                trust_remote_code=True
                            )

                        pipe = pipeline(
                            "text-generation",
                            model=model,
                            tokenizer=tokenizer,
                            max_new_tokens=1024,
                            temperature=0,      # Deterministic for tools
                            do_sample=False,
                            return_full_text=False, # IMPORTANT: don't repeat the prompt
                        )
                        hf_pipe = HuggingFacePipeline(pipeline=pipe)
                        # Pass tokenizer explicitly to ensure ChatML template is used
                        self._chat_model = ChatHuggingFace(
                            llm=hf_pipe,
                            tokenizer=tokenizer
                        )
                        logger.info("[registry] Local Chat Model ready ✓")
                    else:
                        model_name = config.model_name if config and config.model_name else self.settings.CHAT_MODEL
                        logger.info(f"[registry] Using remote Chat Model: {model_name}")
                        from langchain.chat_models import init_chat_model
                        
                        api_key = config.api_key if config and config.api_key else self.settings.CHAT_API_KEY
                        api_url = config.url if config and config.url else self.settings.CHAT_API_URL
                        
                        kwargs = {
                            "model": model_name,
                            "temperature": 0.5,
                        }
                        if api_key:
                            kwargs["api_key"] = api_key
                        if api_url:
                            kwargs["base_url"] = api_url
                            
                        self._chat_model = init_chat_model(**kwargs)
        return self._chat_model

    def reset_model(self, model_type: str) -> None:
        """
        Clears the cached instance of a model so it will be reloaded
        with new settings on the next access.
        """
        if model_type == "vision":
            with self._vision_lock:
                self._vision_generator = None
        elif model_type == "clip":
            with self._clip_lock:
                self._clip_tagger = None
        elif model_type == "embedding":
            with self._nomic_lock:
                self._nomic_embedder = None
        elif model_type == "translator":
            with self._translator_lock:
                self._translator = None
        elif model_type == "chat":
            with self._chat_lock:
                self._chat_model = None
        elif model_type == "ocr":
            # OCR is a singleton by itself in EasyOCRReader, but we can clear its instance
            from src.ai.ocr import EasyOCRReader
            EasyOCRReader._instance = None
        logger.info(f"[registry] Reset model cache for: {model_type}")


# Global access point
registry = AIModelRegistry.get_instance()
