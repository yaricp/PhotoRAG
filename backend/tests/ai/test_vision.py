import pytest
from unittest.mock import patch, MagicMock
import sys

# ATOMIC MOCKS setup
sys.modules['transformers'] = MagicMock()
sys.modules['qwen_vl_utils'] = MagicMock()
sys.modules['torch'] = MagicMock()

from src.ai.vision import QwenVisionGenerator
from src.config import Settings
from src.ai.prompts import PROMPTS

def test_qwen_vision_generator_instantiation():
    settings = Settings()
    generator = QwenVisionGenerator(settings)
    assert generator.model_id == settings.VISION_DESCRIBER_MODEL
    assert generator.system_prompt == PROMPTS["vision_analysis"]["system_prompt"]

@patch('src.ai.vision.Qwen2VLForConditionalGeneration')
@patch('src.ai.vision.AutoProcessor')
@patch('qwen_vl_utils.process_vision_info')
def test_qwen_vision_generator_describe_scene_mock(mock_process, mock_processor_class, mock_model_class):
    settings = Settings()
    generator = QwenVisionGenerator(settings)
    
    # Internal state setup
    generator.model = mock_model_class.from_pretrained.return_value
    generator.processor = mock_processor_class.from_pretrained.return_value
    
    # Mock behavior
    generator.processor.return_value.to.return_value = {'input_ids': [[1]]}
    generator.processor.apply_chat_template.return_value = "template"
    mock_process.return_value = (None, None)
    generator.model.generate.return_value = [[1, 2]]
    generator.processor.batch_decode.return_value = ["A scene."]
    
    description = generator.describe_scene("mock_path.jpg")
    assert description == "A scene."
