# backend/src/ai/vision.py
from src.config import Settings
from src.ai.prompts import PROMPTS

class QwenVisionGenerator:
    def __init__(self, settings: Settings):
        self.model_id = settings.VISION_DESCRIBER_MODEL
        self.system_prompt = PROMPTS["vision_analysis"]["system_prompt"]
        # Actual loading logic (AutoProcessor, Qwen2VLForConditionalGeneration) will happen here
        
    def describe_scene(self, filepath: str) -> str:
        # TDD Mock: Does not run heavy inference during unit tests
        # In production, this will use Qwen2-VL to describe the image
        return "A happy dog playing in the snow outside."
