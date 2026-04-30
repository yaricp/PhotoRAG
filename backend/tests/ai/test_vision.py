import pytest
from unittest.mock import patch, MagicMock
import sys

# ATOMIC MOCKS setup
sys.modules['transformers'] = MagicMock()
sys.modules['qwen_vl_utils'] = MagicMock()


from src.ai.vision import QwenVisionGenerator
from src.config import ML_Settings

def test_qwen_vision_generator_instantiation():
    settings = ML_Settings()
    generator = QwenVisionGenerator()
    assert generator.MODEL_ID == settings.VISION_DESCRIBER_MODEL

@patch('src.ai.vision.Qwen2VLForConditionalGeneration')
@patch('src.ai.vision.AutoProcessor')
@patch('src.ai.vision.process_vision_info')
@patch('src.ai.vision.Image.open')
def test_qwen_vision_generator_describe_scene_mock(mock_image_open, mock_process, mock_processor_class, mock_model_class):
    settings = ML_Settings()
    generator = QwenVisionGenerator()
    
    # Internal state setup
    generator.model = mock_model_class.from_pretrained.return_value
    generator.processor = mock_processor_class.from_pretrained.return_value
    
    # Mock behavior
    generator.processor.return_value.to.return_value = {'input_ids': [[1]]}
    generator.processor.apply_chat_template.return_value = "template"
    mock_process.return_value = (None, None)
    generator.model.generate.return_value = [[1, 2]]
    generator.processor.batch_decode.return_value = ["A scene."]
    
    description = generator.generate_vision_text("mock_path.jpg", prompt_key="describe_scene")
    assert description == "A scene."
