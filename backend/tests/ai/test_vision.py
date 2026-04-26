from unittest.mock import patch, MagicMock
import sys

# Pre-mock transformers to avoid loading environment during unit tests
sys.modules['transformers'] = MagicMock()

from src.ai.vision import QwenVisionGenerator
from src.config import Settings
from src.ai.prompts import PROMPTS

def test_qwen_vision_generator_instantiation():
    settings = Settings()
    generator = QwenVisionGenerator(settings)
    assert generator.model_id == settings.VISION_DESCRIBER_MODEL
    assert generator.system_prompt == PROMPTS["vision_analysis"]["system_prompt"]

def test_qwen_vision_generator_describe_scene_mock():
    settings = Settings()
    generator = QwenVisionGenerator(settings)
    description = generator.describe_scene("mock_path.jpg")
    assert isinstance(description, str)
    assert len(description) > 0
