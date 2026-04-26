import json
from pathlib import Path

def load_prompts() -> dict:
    prompt_path = Path(__file__).parent.parent.parent / "prompts" / "prompts.json"
    with open(prompt_path, "r", encoding="utf-8") as f:
        return json.load(f)

# Automatically exports global dictionary accessible anywhere via `from src.ai.prompts import PROMPTS`
PROMPTS = load_prompts()
