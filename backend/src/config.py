from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    VISION_DESCRIBER_MODEL: str = "Qwen/Qwen2-VL-2B-Instruct"
    PHOTO_EMBEDDER_MODEL: str = "nomic-ai/nomic-embed-text-v1.5"
    DATABASE_DIALECT: str = "postgresql"
    DATABASE_DRIVER: str = "psycopg2"
    DATABASE_HOST: str
    DATABASE_PORT: int
    DATABASE_USER: str
    DATABASE_PASSWORD: str
    DATABASE_NAME: str
    
    model_config = SettingsConfigDict(env_file=".env")

