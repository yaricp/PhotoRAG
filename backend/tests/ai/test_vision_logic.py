import pytest
from unittest.mock import MagicMock, patch
import sys

# ATOMIC MOCKS setup
sys.modules['transformers'] = MagicMock()
sys.modules['qwen_vl_utils'] = MagicMock()
sys.modules['torch'] = MagicMock()

from src.ai.vision import QwenVisionGenerator

@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.VISION_DESCRIBER_MODEL = "Qwen/Qwen2-VL-7B-Instruct"
    return settings

@patch('src.ai.vision.Qwen2VLForConditionalGeneration')
@patch('src.ai.vision.AutoProcessor')
# Updated: Patch the source instead of the module attribute
@patch('qwen_vl_utils.process_vision_info')
def test_describe_scene_logic(mock_process_info, mock_processor_class, mock_model_class, mock_settings):
    # Setup Mocks
    gen = QwenVisionGenerator(mock_settings)
    
    mock_model = mock_model_class.from_pretrained.return_value
    mock_processor = mock_processor_class.from_pretrained.return_value
    
    gen.model = mock_model
    gen.processor = mock_processor
    
    # Mock inputs - MUST BE BATCHED (nested list)
    mock_processor.return_value.to.return_value = {'input_ids': [[1,2,3]]}
    mock_process_info.return_value = (None, None)
    
    # Mock generate output
    mock_model.generate.return_value = [[1,2,3, 4,5,6]] 
    mock_processor.batch_decode.return_value = ["A beautiful landscape."]
    
    result = gen.describe_scene("fake_path.jpg")
    
    assert result == "A beautiful landscape."
