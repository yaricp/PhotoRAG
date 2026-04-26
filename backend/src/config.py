from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    VISION_DESCRIBER_MODEL: str = "Qwen/Qwen2-VL-2B-Instruct"
    PHOTO_EMBEDDER_MODEL: str = "nomic-ai/nomic-embed-text-v1.5"
    DATABASE_URL: str = "postgresql://user:pass@localhost:5432/photodb"
    
    model_config = SettingsConfigDict(env_file=".env")
