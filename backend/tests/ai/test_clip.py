from src.ai.clip import ClipTagger

def test_clip_tagger_instantiation():
    tagger = ClipTagger()
    assert tagger.model_name == "ViT-B-32"
    assert tagger.pretrained == "laion2b_s34b_b79k"

def test_clip_tagger_generate_keywords_mock():
    tagger = ClipTagger()
    keywords = tagger.generate_keywords("mock_path.jpg")
    assert isinstance(keywords, list)
    assert len(keywords) > 0
