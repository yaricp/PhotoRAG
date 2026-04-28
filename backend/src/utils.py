import json
import hashlib
from datetime import datetime
from PIL import Image, ExifTags
from PIL.TiffImagePlugin import IFDRational
from loguru import logger


def extract_exif(image_path: str):
    try:
        with Image.open(image_path) as image:
            exif = image._getexif()
            if not exif:
                logger.info("No EXIF data found")
                return {}

            result = {}
            for tag, value in exif.items():
                tag_name = ExifTags.TAGS.get(tag, tag)
                result[tag_name] = make_json_safe(value)

            logger.info(f"EXIF extracted: {len(result)} fields")
            return result
    except Exception as err:
        logger.warning(f"Failed to extract EXIF: {err}")
        return {}


def make_json_safe(value):
    try:
        if isinstance(value, IFDRational):
            return float(value)

        elif isinstance(value, bytes):
            return value.decode("utf-8", errors="ignore")

        elif isinstance(value, (list, tuple)):
            return [make_json_safe(v) for v in value]

        elif isinstance(value, dict):
            return {k: make_json_safe(v) for k, v in value.items()}

        elif isinstance(value, (int, float, str, bool)) or value is None:
            return value

        else:
            return str(value)

    except Exception as err:
        logger.warning(f"Failed to convert EXIF value: {err}")
        return str(value)


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


def parse_datetime(exif_raw):
    dt = exif_raw.get("DateTimeOriginal") or exif_raw.get("DateTime")
    if not dt:
        return None


def convert_ocr_result_to_json(result):
    output = []
    for box, text, conf in result:
        output.append({
            "box": [[int(x), int(y)] for x, y in box],
            "text": text,
            "confidence": float(conf)
        })
    return output