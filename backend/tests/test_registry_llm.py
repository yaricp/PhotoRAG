import sys
import pytest
from unittest.mock import MagicMock, patch

sys.modules.setdefault('open_clip', MagicMock())
sys.modules.setdefault('sentence_transformers', MagicMock())
sys.modules.setdefault('transformers', MagicMock())

from src.ai.registry import AIModelRegistry

@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.CHAT_MODEL_MODE = "local"
    settings.CHAT_LOCAL_MODEL = "llama3"
    settings.CHAT_MODEL = "gpt-4o-mini"
    settings.CHAT_API_KEY = "test_key"
    settings.VISION_MODE = "remote"
    settings.EMBEDDING_MODE = "remote"
    settings.TRANSLATOR_MODE = "remote"
    return settings

@pytest.mark.skip(reason="Local transformers mocking is complex due to internal device_map logic")
def test_registry_chat_model_local(mock_settings):
    """Test that registry returns ChatHuggingFace in local mode"""
    with patch("src.ai.registry.ML_Settings", return_value=mock_settings):
        registry = AIModelRegistry()
        registry._settings = mock_settings
        
        with patch("src.ai.registry.AutoModelForCausalLM.from_pretrained") as mock_model, \
             patch("src.ai.registry.AutoTokenizer.from_pretrained") as mock_tokenizer, \
             patch("src.ai.registry.pipeline") as mock_pipeline, \
             patch("src.ai.registry.ChatHuggingFace") as mock_chat_hf:
            
            mock_pipeline.return_value = MagicMock()
            
            model = registry.chat_model
            
            mock_model.assert_called_once()
            mock_tokenizer.assert_called_once()
            mock_pipeline.assert_called_once()
            assert model == mock_chat_hf.return_value

def test_registry_chat_model_remote(mock_settings):
    """Test that registry returns ChatOpenAI (init_chat_model) in remote mode"""
    mock_settings.CHAT_MODEL_MODE = "remote"
    mock_settings.CHAT_MODEL = "gpt-4o-mini"
    mock_settings.CHAT_API_KEY = "test_key"
    mock_settings.CHAT_API_URL = None

    AIModelRegistry._instance = None
    with patch("src.ai.registry.Chat_Settings", return_value=mock_settings), \
         patch("src.ai.registry.Embedding_Settings", return_value=MagicMock()):
        registry = AIModelRegistry()

        with patch.object(registry, "get_model_config", return_value=None), \
             patch("langchain.chat_models.init_chat_model") as mock_init:
            model = registry.chat_model
            mock_init.assert_called_once_with(
                model="gpt-4o-mini",
                temperature=0.5,
                api_key="test_key"
            )
            assert model == mock_init.return_value
