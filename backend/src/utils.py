import hashlib
import json
import os
import shutil
from datetime import datetime
from typing import Optional

from loguru import logger
from PIL import ExifTags, Image
from PIL.TiffImagePlugin import IFDRational


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
    """
    Robustly extract and parse datetime from EXIF data.
    Returns a Python datetime object for compatibility with SQLAlchemy/SQLite.
    """
    if not exif_raw:
        return None

    # EXIF date fields in priority order
    date_keys = ["DateTimeOriginal", "DateTimeDigitized", "DateTime"]
    dt_str = None

    for key in date_keys:
        val = exif_raw.get(key)
        if val and isinstance(val, str) and val.strip():
            # Remove null bytes or weird non-printable chars often found in EXIF
            clean_val = val.strip().replace("\x00", "")
            if clean_val and clean_val != "0000:00:00 00:00:00":
                dt_str = clean_val
                break

    if not dt_str:
        return None

    logger.info(f"[parse_datetime] Attempting to parse: {dt_str}")

    # Try the standard EXIF format first
    formats = ["%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"]
    for fmt in formats:
        try:
            return datetime.strptime(dt_str, fmt)
        except (ValueError, TypeError):
            continue

    logger.warning(f"[parse_datetime] Failed to parse any known format for: {dt_str}")
    return None


def convert_ocr_result_to_json(result):
    output = []
    for box, text, conf in result:
        output.append({"box": [[int(x), int(y)] for x, y in box], "text": text, "confidence": float(conf)})
    return output


def archive_photos_to_zip(file_paths: list, zip_path: str) -> tuple:
    """
    Append files to a zip archive and delete the originals from disk.

    Returns:
        added   — dict mapping arcname (filename in zip) → original absolute path
        skipped — list of original paths that were missing and not archived
    """
    import zipfile

    added: dict = {}  # arcname → original_path
    skipped: list = []
    with zipfile.ZipFile(zip_path, "a") as zf:
        for fp in file_paths:
            if not os.path.exists(fp):
                skipped.append(fp)
                continue
            arcname = os.path.basename(fp)
            zf.write(fp, arcname)
            added[arcname] = fp
    # Delete originals only after the zip is safely closed and flushed
    for fp in added.values():
        try:
            os.remove(fp)
            logger.info(f"Deleted original after archiving: {fp}")
        except OSError as e:
            logger.warning(f"Could not delete original {fp}: {e}")
    logger.info(f"archive_photos_to_zip: added {len(added)}, skipped {len(skipped)}")
    return added, skipped


def resize_image(image_path: str, width: int, height: int) -> str:
    try:
        with Image.open(image_path) as image:
            image = image.resize((width, height))
            new_path = image_path.replace(".jpg", "_resized.jpg")
            image.save(new_path)
            logger.info(f"Image resized: {new_path}")
            return new_path
    except Exception as err:
        logger.warning(f"Failed to resize image: {err}")
        return ""


def check_if_file_is_image(image_path: str) -> bool:
    try:
        with Image.open(image_path) as image:
            image.verify()
            return True
    except Exception as err:
        logger.warning(f"Failed to verify image: {err}")
        return False


def make_dir_by_datetime(photo_created_at: datetime, destination_root_folder: str) -> str:
    """
    Returns the path to the folder where the photo should be moved, based on its creation date.
    Creates the folder if it doesn't exist.
    """
    year_folder = photo_created_at.strftime("%Y")
    month_folder = photo_created_at.strftime("%m")
    day_folder = photo_created_at.strftime("%d")
    destination_path = os.path.join(destination_root_folder, year_folder, month_folder, day_folder)
    os.makedirs(destination_path, exist_ok=True)
    return destination_path


def move_photo(path: str, destination_root_folder: str):
    """
    Move file to the destination folder based on its creation date.
    """
    try:
        stat = os.stat(path)
        file_created_at = datetime.fromtimestamp(getattr(stat, "st_birthtime", stat.st_ctime))
        logger.info(f"File created at: {file_created_at}")
        file_name = os.path.basename(path)
        new_path = make_dir_by_datetime(file_created_at, destination_root_folder)
        destination = os.path.join(new_path, file_name)
        shutil.move(path, destination)
        logger.info(f"File moved to: {destination}")
        return destination
    except Exception as err:
        logger.warning(f"Failed to move file {path} to {destination_root_folder}: {err}")
        return ""


def get_photo_capture_date(photo_path: str) -> Optional[datetime]:
    """Gets photo capture date from EXIF data."""
    try:
        exif_raw = extract_exif(photo_path)
        return parse_datetime(exif_raw)
    except Exception as err:
        logger.warning(f"Failed to get photo capture date for {photo_path}: {err}")
        return None
