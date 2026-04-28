from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv


load_dotenv()


class Database_Settings(BaseSettings):
    DATABASE_DIALECT: str = "postgresql"
    DATABASE_DRIVER: str = "psycopg2"
    DATABASE_HOST: str
    DATABASE_PORT: int
    DATABASE_USER: str
    DATABASE_PASSWORD: str
    DATABASE_NAME: str
    
    # model_config = SettingsConfigDict(env_file=".env")


class Api_Settings(BaseSettings):
    API_HOST: str = "localhost"
    API_PORT: int = 8001
    API_TOKEN: str

    # model_config = SettingsConfigDict(env_file=".env")


class ML_Settings(BaseSettings):
    VISION_DESCRIBER_MODEL: str = "Qwen/Qwen2-VL-2B-Instruct"
    PHOTO_EMBEDDER_MODEL: str = "nomic-ai/nomic-embed-text-v1.5"
    RESIZE_FOR_DESCRIPTION_Y: int = 448
    RESIZE_FOR_DESCRIPTION_X: int = 448
    RESIZE_FOR_DESCRIPTION: tuple[int, int] = (
        RESIZE_FOR_DESCRIPTION_Y,
        RESIZE_FOR_DESCRIPTION_X
    )
    RESIZE_FOR_DETECTION_Y: int = 224
    RESIZE_FOR_DETECTION_X: int = 224
    RESIZE_FOR_DETECTION: tuple[int, int] = (
        RESIZE_FOR_DETECTION_Y,
        RESIZE_FOR_DETECTION_X
    )


class CLIP_Settings(BaseSettings):
    CLIP_MODEL: str = "ViT-B-32"
    PRETRAINED: str = "laion2b_s34b_b79k"
    CSV_PATH: str = "data/class-descriptions-boxable.csv"
    NPY_PATH: str = "data/tags_features.npy"
    TAGS_LIST_PATH: str = "data/tags_list.txt"
    TAGS_CLIP_THRESHOLD: float = 0.26
    VOCAB_URL: str = "https://storage.googleapis.com/openimages/v7/oidv7-class-descriptions-boxable.csv"
    CATEGORIES_NPY_PATH: str = "data/categories_features.npy"
    CATEGORIES_HASH_PATH: str = "data/categories_hash.txt"
    CATEGORIES_CLIP_THRESHOLD: float = 0.2


