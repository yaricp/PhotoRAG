"""
OCR worker queue.

Responsibilities:
- Load the OCR engine (model name read from main DB at startup).
- Accept tasks: extract text from an image file.
- Save results to task_results.db. Zero access to the main photo DB.
"""
import os
import time
import json
import threading

from huey import SqliteHuey
from loguru import logger

from src.db.task_results import save_result, save_error
from src.queues.queue_config import get_model_name_from_db

_DB_PATH = os.path.join(os.getcwd(), "../db.sqlite3")
_DEFAULT_MODEL_NAME = "easyocr"

ocr_queue = SqliteHuey(
    "ocr",
    filename=os.path.join(os.getcwd(), "../ocr.sqlite3")
)

_reader = None
_lock = threading.Lock()


def _get_reader():
    global _reader
    if _reader is None:
        with _lock:
            if _reader is None:
                model_name = get_model_name_from_db(_DB_PATH, "ocr", _DEFAULT_MODEL_NAME)
                logger.info(f"[ocr_queue] Loading OCR engine: {model_name}")
                from src.ai.ocr import EasyOCRReader
                _reader = EasyOCRReader.get_instance()
                logger.info(f"[ocr_queue] OCR engine ready: {model_name}")
    return _reader


@ocr_queue.on_startup()
def warm():
    """Load OCR engine into RAM before accepting tasks."""
    _get_reader()


@ocr_queue.task()
def call_local_ocr_model(task_id: str, file_path: str) -> None:
    """
    Extract text from an image file.

    Result stored as JSON: {"text": "<extracted text or empty string>"}
    """
    logger.info(f"[ocr_queue] Received task for {file_path}")
    start_time = time.time()
    try:
        reader = _get_reader()
        with _lock:
            from src.ai.ocr import extract_text_from_image
            text = extract_text_from_image(file_path)
        save_result(task_id, json.dumps({"text": text or ""}))
        logger.info(f"[ocr_queue] Completed task for {file_path} in {time.time() - start_time:.2f}s")
    except Exception as exc:
        logger.error(f"[ocr_queue] OCR failed for {file_path}: {exc}")
        save_error(task_id, str(exc))
