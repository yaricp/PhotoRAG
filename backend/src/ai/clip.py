import open_clip
import torch

class ClipTagger:
    def __init__(self):
        self.model_name = "ViT-B-32"
        self.pretrained = "laion2b_s34b_b79k"
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = None
        self.preprocess = None

    def download(self):
        """Pre-downloads the models and weights."""
        open_clip.create_model_and_transforms(self.model_name, self.pretrained)

    def load(self):
        if not self.model:
            self.model, _, self.preprocess = open_clip.create_model_and_transforms(
                self.model_name, self.pretrained, device=self.device
            )

    def generate_keywords(self, filepath: str) -> list[str]:
        # Implementation placeholder
        return ["cat", "dog", "snow", "outdoor"]
