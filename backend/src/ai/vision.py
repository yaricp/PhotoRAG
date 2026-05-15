import torch
from loguru import logger
from PIL import Image
from transformers import AutoProcessor, Qwen2VLForConditionalGeneration
from qwen_vl_utils import process_vision_info

from src.config import Vision_Settings as ML_Settings
from src.ai.prompts import get_prompt


class QwenVisionGenerator:
    """
    This class is a wrapper around the Qwen2VLForConditionalGeneration model.
    It is used to generate text descriptions of images.
    """
    settings = ML_Settings()
    RESIZE_FOR_DESCRIPTION = settings.RESIZE_FOR_DESCRIPTION
    RESIZE_FOR_DETECTION = settings.RESIZE_FOR_DETECTION
    MODEL_ID = settings.VISION_DESCRIBER_MODEL

    def __init__(self):
        self.processor = None
        self.model = None
        if torch.cuda.is_available():
            self.device = "cuda"
        elif torch.backends.mps.is_available():
            self.device = "mps"
        else:
            self.device = "cpu"

    def download(self):
        """Pre-downloads the models and weights from HuggingFace."""
        AutoProcessor.from_pretrained(self.MODEL_ID)
        Qwen2VLForConditionalGeneration.from_pretrained(
            self.MODEL_ID, torch_dtype="auto"
        )

    def load(self):
        if not self.model:
            logger.info(f"Vision: Loading {self.MODEL_ID} on {self.device}...")
            self.model = Qwen2VLForConditionalGeneration.from_pretrained(
                self.MODEL_ID, 
                torch_dtype=torch.float16
            ).to(self.device)
            self.processor = AutoProcessor.from_pretrained(self.MODEL_ID)
            self.model.eval()
            logger.info(f"Vision: {self.MODEL_ID} loaded on {self.device}")

    def generate_vision_text(
        self, file_path: str, prompt_key: str = "describe_scene"
    ) -> str:
        """Universal vision generation using prompts from central registry."""
        # from qwen_vl_utils import process_vision_info
        self.load()

        image = Image.open(file_path).convert("RGB")
        
        if prompt_key  == "describe_scene":
            image = image.resize(self.RESIZE_FOR_DESCRIPTION)
        elif prompt_key == "is_document":
            image = image.resize(self.RESIZE_FOR_DETECTION)
        
        # Fetch prompt fresh from DB on every call (no cache)
        try:
            prompt_text = get_prompt(f"vision_analysis.{prompt_key}")
        except KeyError:
            prompt_text = get_prompt("vision_analysis.describe_scene")

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": prompt_text},
                ],
            }
        ]

        # Preparation
        text = self.processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        image_inputs, video_inputs = process_vision_info(messages)
        inputs = self.processor(
            text=[text],
            images=image_inputs,
            videos=video_inputs,
            padding=True,
            return_tensors="pt",
        )
        inputs = inputs.to(self.device)

        # Inference
        with torch.no_grad():
            generated_ids = self.model.generate(**inputs, max_new_tokens=128)
            generated_ids_trimmed = [
                out_ids[len(in_ids) :] for in_ids, out_ids in zip(inputs["input_ids"], generated_ids)
            ]
            output_text = self.processor.batch_decode(
                generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
            )
            
        return output_text[0] if output_text else ""
