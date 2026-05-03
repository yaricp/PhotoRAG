import pytest
from unittest.mock import MagicMock, patch
import sys

# ATOMIC MOCK setup to prevent actual model loading during registry test
sys.modules['open_clip'] = MagicMock()

sys.modules['sentence_transformers'] = MagicMock()
sys.modules['transformers'] = MagicMock()

from src.ai.registry import AIModelRegistry

def test_registry_is_singleton():
    reg1 = AIModelRegistry.get_instance()
    reg2 = AIModelRegistry.get_instance()
    assert reg1 is reg2

@patch('src.ai.clip.ClipTagger')
def test_lazy_loading_clip(mock_clip_class):
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

@patch('sentence_transformers.SentenceTransformer')
def test_lazy_loading_nomic(mock_st_class):
    AIModelRegistry._instance = None
    reg = AIModelRegistry.get_instance()
    
    embedder1 = reg.nomic_embedder
    embedder2 = reg.nomic_embedder
    
    assert mock_st_class.call_count == 1
    assert embedder1 is embedder2
