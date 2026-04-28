from transformers import AutoProcessor, Qwen2VLForConditionalGeneration
from src.config import ML_Settings
from src.ai.prompts import PROMPTS
import torch
from loguru import logger


class QwenVisionGenerator:
    def __init__(self, settings: ML_Settings):
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
            logger.info(f"Vision: Loading {self.model_id} on {self.device}...")
            self.model = Qwen2VLForConditionalGeneration.from_pretrained(
                self.model_id, 
                torch_dtype="auto", 
                device_map="auto"
            )
            self.processor = AutoProcessor.from_pretrained(self.model_id)
            self.model.eval()

    def generate_vision_text(self, filepath: str, prompt_key: str = "describe_scene") -> str:
        """Universal vision generation using prompts from central registry."""
        from qwen_vl_utils import process_vision_info
        self.load()
        
        # Pull prompt from registry
        prompt_text = PROMPTS["vision_analysis"].get(
            prompt_key, 
            PROMPTS["vision_analysis"]["describe_scene"]
        )

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": f"file://{filepath}"},
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

    def describe_scene(self, filepath: str) -> str:
        """Legacy wrapper for scene description."""
        return self.generate_vision_text(filepath, prompt_key="describe_scene")
