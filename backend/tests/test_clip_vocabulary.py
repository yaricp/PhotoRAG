import pytest
import os
import numpy as np
from unittest.mock import MagicMock, patch, mock_open

# We don't need atomic mocks because we use @patch later and want real open_clip to be importable
from src.ai.clip import ClipTagger

@pytest.fixture
def clip_tagger():
    return ClipTagger()

def test_vocabulary_normalization():
    tagger = ClipTagger()
    raw_tags = ["  Nature ", "MOUNTAINS", "Nature"]
    normalized = tagger._normalize_tags(raw_tags)
    assert "nature" in normalized
    assert "mountains" in normalized
    assert len(normalized) == 2

@patch('requests.get')
def test_download_vocabulary_csv(mock_get, clip_tagger):
    csv_content = "/m/0abc,Dog\n/m/0xyz,Cat"
    mock_get.return_value.status_code = 200
    mock_get.return_value.text = csv_content
    
    with patch("builtins.open", mock_open(read_data=csv_content)):
         tags = clip_tagger.download_vocabulary()
         assert "dog" in tags
         assert "cat" in tags

@patch('src.ai.clip.open_clip')
def test_compute_embeddings_saves_npy(mock_open_clip, clip_tagger, tmp_path):
    # Setup mocks
    mock_model = MagicMock()
    mock_open_clip.create_model_and_transforms.return_value = (mock_model, None, None)
    mock_open_clip.tokenize.return_value = MagicMock()
    
    # Mock return values for features and their chain of operations
    fake_array = np.random.rand(2, 512).astype(np.float32)
    mock_features = MagicMock()
    
    # Division result must return something that has .detach().cpu().numpy()
    mock_div_result = MagicMock()
    mock_div_result.detach.return_value.cpu.return_value.numpy.return_value = fake_array
    
    mock_model.encode_text.return_value = mock_features
    # Mock / operator
    mock_features.__truediv__.return_value = mock_div_result
    mock_features.norm.return_value = 1.0
    
    npy_path = os.path.join(tmp_path, "tags.npy")
    with patch.object(clip_tagger, 'NPY_PATH', npy_path):
        # We need to also patch TAGS_LIST_PATH to avoid polluting project root
        with patch.object(clip_tagger, 'TAGS_LIST_PATH', os.path.join(tmp_path, "tags.txt")):
            clip_tagger.compute_embeddings_tags(["dog", "cat"])
            assert os.path.exists(npy_path)
            data = np.load(npy_path)
            assert data.shape == (2, 512)
