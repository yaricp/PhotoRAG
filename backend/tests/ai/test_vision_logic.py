import sys
from unittest.mock import MagicMock, patch

# ATOMIC MOCKS setup
sys.modules["transformers"] = MagicMock()
sys.modules["qwen_vl_utils"] = MagicMock()


from src.ai.vision import QwenVisionGenerator


@patch("src.ai.vision.Qwen2VLForConditionalGeneration")
@patch("src.ai.vision.AutoProcessor")
@patch("src.ai.vision.process_vision_info")
@patch("src.ai.vision.Image.open")
def test_generate_vision_text_logic(mock_image_open, mock_process_info, mock_processor_class, mock_model_class):
    # Setup Mocks
    gen = QwenVisionGenerator()

    mock_model = mock_model_class.from_pretrained.return_value
    mock_processor = mock_processor_class.from_pretrained.return_value

    gen.model = mock_model
    gen.processor = mock_processor

    # Mock inputs - MUST BE BATCHED (nested list)
    mock_processor.return_value.to.return_value = {"input_ids": [[1, 2, 3]]}
    mock_process_info.return_value = (None, None)

    # Mock generate output
    mock_model.generate.return_value = [[1, 2, 3, 4, 5, 6]]
    mock_processor.batch_decode.return_value = ["A beautiful landscape."]

    result = gen.generate_vision_text("fake_path.jpg", prompt_key="describe_scene")

    assert result == "A beautiful landscape."
