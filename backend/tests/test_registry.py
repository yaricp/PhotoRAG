import sys
from unittest.mock import MagicMock, patch

# ATOMIC MOCK setup to prevent actual model loading during registry test
sys.modules.setdefault("open_clip", MagicMock())
sys.modules.setdefault("sentence_transformers", MagicMock())
sys.modules.setdefault("transformers", MagicMock())
sys.modules.setdefault("src.ai.clip", MagicMock())

# Earlier test files mock src.ai and src.ai.registry as MagicMocks.
# Evict them so we import the real AIModelRegistry class here.
sys.modules.pop("src.ai", None)
sys.modules.pop("src.ai.registry", None)

from src.ai.registry import AIModelRegistry


def test_registry_is_singleton():
    reg1 = AIModelRegistry.get_instance()
    reg2 = AIModelRegistry.get_instance()
    assert reg1 is reg2


@patch("src.ai.registry.AIModelRegistry.get_model_config")
@patch("src.ai.clip.ClipTagger")
def test_lazy_loading_clip(mock_clip_class, mock_get_config):
    mock_get_config.return_value = None  # Fallback to settings
    mock_instance = mock_clip_class.return_value
    # Reset registry for clean test
    AIModelRegistry._instance = None
    reg = AIModelRegistry.get_instance()

    # First call - should instantiate
    tagger1 = reg.clip_tagger
    assert mock_clip_class.called

    # Second call - should return cached
    tagger2 = reg.clip_tagger
    assert mock_clip_class.call_count == 1
    assert tagger1 is tagger2


@patch("src.ai.registry.AIModelRegistry.get_model_config")
@patch("sentence_transformers.SentenceTransformer")
def test_lazy_loading_nomic(mock_st_class, mock_get_config):
    mock_get_config.return_value = None  # Fallback to settings
    AIModelRegistry._instance = None
    reg = AIModelRegistry.get_instance()

    embedder1 = reg.nomic_embedder
    embedder2 = reg.nomic_embedder

    assert mock_st_class.call_count == 1
    assert embedder1 is embedder2
