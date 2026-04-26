# backend/src/ai/clip.py

class ClipTagger:
    def __init__(self):
        self.model_name = "ViT-B-32"
        self.pretrained = "laion2b_s34b_b79k"
        # Actual loading logic (e.g. open_clip.create_model_and_transforms) will happen in non-mocked execution
        
    def generate_keywords(self, filepath: str) -> list[str]:
        # TDD Mock: Does not download LAION weights during tests
        # In production, this will use the model to find top classes
        return ["cat", "dog", "snow", "outdoor"]
