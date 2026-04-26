import os
from src.config import Settings

def test_settings_loads_env_vars(monkeypatch):
    monkeypatch.setenv("VISION_DESCRIBER_MODEL", "Qwen/test-model")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/testdb")
    settings = Settings()
    assert settings.VISION_DESCRIBER_MODEL == "Qwen/test-model"
    assert settings.DATABASE_URL == "postgresql://user:pass@localhost:5432/testdb"
