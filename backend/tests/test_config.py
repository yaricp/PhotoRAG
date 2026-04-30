import os
from src.config import ML_Settings

def test_settings_loads_env_vars(monkeypatch):
    monkeypatch.setenv("VISION_DESCRIBER_MODEL", "Qwen/test-model")
    settings = ML_Settings()
    assert settings.VISION_DESCRIBER_MODEL == "Qwen/test-model"
