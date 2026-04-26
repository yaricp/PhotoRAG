from transformers import AutoProcessor, Qwen2VLForConditionalGeneration
from src.config import Settings
from src.ai.prompts import PROMPTS
import torch

class QwenVisionGenerator:
    def __init__(self, settings: Settings):
        self.model_id = settings.VISION_DESCRIBER_MODEL
        self.system_prompt = PROMPTS["vision_analysis"]["system_prompt"]
        self.device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
        self.processor = None
        self.model = None

    def download(self):
        """Pre-downloads the models and weights from HuggingFace."""
        AutoProcessor.from_pretrained(self.model_id)
        Qwen2VLForConditionalGeneration.from_pretrained(
            self.model_id, torch_dtype="auto"
        )

    def load(self):
        if not self.model:
            self.model = Qwen2VLForConditionalGeneration.from_pretrained(
                self.model_id, torch_dtype="auto", device_map="auto"
            )
            self.processor = AutoProcessor.from_pretrained(self.model_id)

    def describe_scene(self, filepath: str) -> str:
        # Implementation placeholder
        return "A happy dog playing in the snow outside."
