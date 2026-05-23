# src/config.py

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

from src.data_dir import resolve_app_data_dir

_APP_DATA_DIR = resolve_app_data_dir()
(_APP_DATA_DIR / "data").mkdir(exist_ok=True)

# Load .env from APP_DATA_DIR first, then fall back to project-root .env
load_dotenv(_APP_DATA_DIR / ".env", override=False)
load_dotenv(override=False)


class Main_Settings(BaseSettings):
    LANGUAGES: list[str] = ["en", "ru", "es"]
    DEFAULT_LANGUAGE: str = "en"


class TaskQueue_Settings(BaseSettings):
    # How long to wait for a single model task result before giving up.
    # Must be large enough to cover (MAX_CONCURRENT_PIPELINES × slowest model time).
    # Vision on CPU can take 30s/photo; with 8 concurrent photos worst-case is 240s.
    TASK_RESULT_TIMEOUT: float = 600.0
    TASK_RESULT_POLL_INTERVAL: float = 0.5     # seconds between polls
    TASK_RESULT_DB_PATH: str = str(_APP_DATA_DIR / "task_results.db")
    MAX_CONCURRENT_PIPELINES: int = 20          # max photos processed simultaneously
    # Log a "still waiting" heartbeat this often while polling (seconds)
    TASK_RESULT_LOG_INTERVAL: float = 30.0


class Database_Settings(BaseSettings):
    DATABASE_DIALECT: str = "sqlite"
    DATABASE_NAME: str = str(_APP_DATA_DIR / "db.sqlite3")
    TASK_RESULTS_DATABASE_NAME: str = str(_APP_DATA_DIR / "task_results.db")

    @property
    def DATABASE_PATH(self) -> str:
        return os.path.abspath(self.DATABASE_NAME)

    @property
    def TASK_RESULTS_DATABASE_PATH(self) -> str:
        return os.path.abspath(self.TASK_RESULTS_DATABASE_NAME)


class Api_Settings(BaseSettings):
    API_HOST: str = "localhost"
    API_PORT: int = 8001
    API_TOKEN: str = "secret"


def _data(name: str) -> str:
    """Return absolute path to a mutable data file inside APP_DATA_DIR/data/."""
    return str(_APP_DATA_DIR / "data" / name)


class CLIP_Settings(BaseSettings):
    CLIP_MODEL: str = "ViT-B-32"
    CLIP_MODE: str = "local"        # local | remote
    CLIP_API_URL: str = ""
    CLIP_API_KEY: str = ""
    PRETRAINED: str = "laion2b_s34b_b79k"
    # Read-only vocab files: keep relative so dev and bundled app can both find them
    CSV_PATH: str = "data/class-descriptions-boxable.csv"
    TAGS_LIST_PATH: str = "data/tags_list.txt"
    TAGS_CLIP_THRESHOLD: float = 0.26
    VOCAB_URL: str = "https://storage.googleapis.com/openimages/v7/oidv7-class-descriptions-boxable.csv"
    # Mutable caches — live in APP_DATA_DIR/data/
    NPY_PATH: str = _data("tags_features.npy")
    TAGS_MODEL_HASH_PATH: str = _data("tags_model.hash")
    TAGS_NAMES_PATH: str = _data("tags_names.json")
    CATEGORIES_NPY_PATH: str = _data("categories_features.npy")
    CATEGORIES_HASH_PATH: str = _data("categories_hash.txt")
    CATEGORIES_MODEL_HASH_PATH: str = _data("categories_model.hash")
    CATEGORIES_NAMES_PATH: str = _data("categories_names.json")
    CATEGORIES_CLIP_THRESHOLD: float = 0.2

    @property
    def local_models(self) -> list[str]:
        """Список моделей которые нужно скачать и запустить как процесс"""
        result = []
        if self.CLIP_MODE == "local":
            result.append("clip")
        return result


class Vision_Settings(BaseSettings):
    # Vision
    VISION_MODE: str = "local"           # local | remote
    VISION_DESCRIBER_MODEL: str = "Qwen/Qwen2-VL-2B-Instruct"
    VISION_API_URL: str = ""
    VISION_API_KEY: str = ""
    RESIZE_FOR_DESCRIPTION: tuple[int, int] = (448, 448)
    RESIZE_FOR_DETECTION: tuple[int, int] = (224, 224)


class Embedding_Settings(BaseSettings):
    # Embedding
    EMBEDDING_MODE: str = "local"        # local | remote
    PHOTO_EMBEDDER_MODEL: str = "nomic-ai/nomic-embed-text-v1.5"
    EMBEDDING_API_URL: str = ""
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_SIMILARITY_LIMIT: float = 0.89  # cosine distance threshold; lower = stricter


class Translation_Settings(BaseSettings):
    # Translator
    TRANSLATOR_MODEL: str = "facebook/nllb-200-distilled-600M"
    TRANSLATOR_MODE: str = "local"
    TRANSLATOR_API_URL: str = ""
    TRANSLATOR_API_KEY: str = ""


class OCR_Settings(BaseSettings):
    # OCR
    OCR_MODE: str = "local"
    OCR_MODEL: str = "microsoft/trocr-small-handwritten"
    OCR_API_URL: str = ""
    OCR_API_KEY: str = ""


class Chat_Settings(BaseSettings):
    # Chat
    CHAT_MODEL_MODE: str = "remote"           # local | remote
    CHAT_MODEL: str = "gpt-4o-mini"
    CHAT_LOCAL_MODEL: str = "Qwen/Qwen2.5-Coder-3B-Instruct"
    CHAT_API_URL: str = ""
    CHAT_API_KEY: str = ""

    # @property
    # def local_models(self) -> list[str]:
    #     """Список моделей которые нужно скачать и запустить как процесс"""
    #     result = []
    #     if self.VISION_MODE == "local":
    #         result.append("vision")
    #     if self.EMBEDDING_MODE == "local":
    #         result.append("embedding")
    #     if self.TRANSLATOR_MODE == "local":
    #         result.append("translate")
    #     return result
