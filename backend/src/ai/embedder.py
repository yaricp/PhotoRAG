from src.config import Settings

class PhotoEmbedder:
    def __init__(self):
        self.settings = Settings()
        self.model_name = self.settings.PHOTO_EMBEDDER_MODEL
        
    def generate_embedding(self, text: str) -> list[float]:
        # Returns a dummy 768 vector representation for TDD testing until real weights are explicitly loaded
        return [0.0] * 768
