# src/config.py

from pydantic_settings import BaseSettings
from dotenv import load_dotenv


load_dotenv()


class Database_Settings(BaseSettings):
    DATABASE_DIALECT: str = "sqlite"
    DATABASE_NAME: str = "../db.sqlite3"


class Api_Settings(BaseSettings):
    API_HOST: str = "localhost"
    API_PORT: int = 8001
    API_TOKEN: str = "secret"


class CLIP_Settings(BaseSettings):
    CLIP_MODEL: str = "ViT-B-32"
    PRETRAINED: str = "laion2b_s34b_b79k"
    CSV_PATH: str = "data/class-descriptions-boxable.csv"
    NPY_PATH: str = "data/tags_features.npy"
    TAGS_LIST_PATH: str = "data/tags_list.txt"
    TAGS_CLIP_THRESHOLD: float = 0.26
    VOCAB_URL: str = "https://storage.googleapis.com/openimages/v7/oidv7-class-descriptions-boxable.csv"
    
    TAGS_MODEL_HASH_PATH: str = "data/tags_model.hash"

    CATEGORIES_NPY_PATH: str = "data/categories_features.npy"
    CATEGORIES_HASH_PATH: str = "data/categories_hash.txt"
    CATEGORIES_MODEL_HASH_PATH: str = "data/categories_model.hash"
    CATEGORIES_CLIP_THRESHOLD: float = 0.2


class ML_Settings(BaseSettings):
    # Vision
    VISION_MODE: str = "local"           # local | remote
    VISION_DESCRIBER_MODEL: str = "Qwen/Qwen2-VL-2B-Instruct"
    VISION_API_URL: str = ""
    VISION_API_KEY: str = ""
    RESIZE_FOR_DESCRIPTION: tuple[int, int] = (448, 448)
    RESIZE_FOR_DETECTION: tuple[int, int] = (224, 224)

    # Embedding
    EMBEDDING_MODE: str = "local"        # local | remote
    PHOTO_EMBEDDER_MODEL: str = "nomic-ai/nomic-embed-text-v1.5"
    EMBEDDING_API_URL: str = ""
    EMBEDDING_API_KEY: str = ""

    @property
    def local_models(self) -> list[str]:
        """Список моделей которые нужно скачать и запустить как процесс"""
        result = ["clip"]  # CLIP всегда local
        if self.VISION_MODE == "local":
            result.append("vision")
        if self.EMBEDDING_MODE == "local":
            result.append("embedding")
        return result
