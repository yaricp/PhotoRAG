import numpy as np
from unittest.mock import MagicMock, patch
import sys

# Pre-mock to avoid loading environment
sys.modules['open_clip'] = MagicMock()
sys.modules['torch'] = MagicMock()

from src.ai.clip import ClipTagger

def test_clip_tagger_instantiation():
    tagger = ClipTagger()
    assert tagger.model_name == "ViT-B-32"
    assert tagger.pretrained == "laion2b_s34b_b79k"

@patch('src.ai.clip.open_clip')
def test_clip_tagger_find_tags_mock(mock_open_clip):
    # Setup tagger with fake vocabulary and model
    tagger = ClipTagger()
    tagger.tags = ["nature", "mountain"]
    tagger.tags_features = np.random.rand(2, 512).astype(np.float32)
    tagger.preprocess = MagicMock() 
    tagger.device = "cpu"
    
    # Mock the internal model
    mock_model = MagicMock()
    tagger.model = mock_model
    
    # Mock image_features calculation
    mock_raw_feat = MagicMock()
    mock_raw_feat.norm.return_value = 1.0
    mock_model.encode_image.return_value = mock_raw_feat
    
    # CRITICAL: Mock the result of division
    mock_norm_feat = MagicMock()
    mock_raw_feat.__truediv__.return_value = mock_norm_feat
    
    # The normalized features must return a real array
    mock_norm_feat.cpu.return_value.numpy.return_value = np.random.rand(1, 512).astype(np.float32)
    
    with patch.object(tagger, 'load', return_value=None):
        with patch('PIL.Image.open', return_value=MagicMock()):
             keywords = tagger.find_tags("mock_path.jpg")
             assert isinstance(keywords, list)
             assert len(keywords) == 2
             # Updated for (tag, score) tuples
             labels = [t for t, s in keywords]
             assert "nature" in labels or "mountain" in labels
             
@patch('requests.get')
def test_clip_tagger_download_vocab_logic(mock_get):
    tagger = ClipTagger()
    mock_get.return_value.status_code = 200
    mock_get.return_value.text = "/m/01,dog\n/m/02,cat"
    
    with patch("builtins.open", MagicMock()):
        with patch("csv.reader", return_value=[["/m/01", "dog"], ["/m/02", "cat"]]):
            tags = tagger.download_vocabulary()
            assert "dog" in tags
            assert "cat" in tags
