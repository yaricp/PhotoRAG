import json
from pathlib import Path

def load_prompts() -> dict:
    prompt_path = Path(__file__).parent.parent.parent / "prompts" / "prompts.json"
    with open(prompt_path, "r", encoding="utf-8") as f:
        return json.load(f)

# Automatically exports global dictionary accessible anywhere via `from src.ai.prompts import PROMPTS`
PROMPTS = load_prompts()


def expand_tags(tags):
    if not tags:
        return ""

    tag_list = [tag.name for tag in tags]
    return ", ".join(tag_list)


def build_photo_text_for_embedding(
    description: str, tags:list[str], categories:list[str], location: str
) -> str:
    parts = []

    if description:
        parts.append(f"A detailed photo of {description}")

    if tags:
        tags_str = ", ".join(tags)
        parts.append(f"It contains: {tags_str}")

    if categories:
        categories_str = ", ".join(categories)
        parts.append(f"This is related to {categories_str}")

    if location and location != "Unknown Location":
        parts.append(f"Taken at {location}")

    return ". ".join(parts)