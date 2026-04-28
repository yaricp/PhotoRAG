import json
import hashlib
from typing import Dict, List


def load_categories_from_json(path: str) -> list:
    """
    Returns:
        [
            {"id": 8, "name": "food", "prompt": "..."},
            ...
        ]
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data


def generate_file_hash(filepath: str) -> str:
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()