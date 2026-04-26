from src.ai.embedder import PhotoEmbedder

def test_embedder_instantiation():
    embedder = PhotoEmbedder()
    assert embedder.model_name == "nomic-ai/nomic-embed-text-v1.5"
