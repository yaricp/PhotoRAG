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
from src.queues.queue_config import read_model_config_from_db

from src.config import Database_Settings as _DB_Settings
_DB_PATH = _DB_Settings().DATABASE_PATH
_DEFAULT_MODEL_NAME = "easyocr"

ocr_queue = SqliteHuey(
    "ocr",
    filename=os.path.join(os.getcwd(), "../ocr.sqlite3")
)

_reader = None
_reader_loaded = False
_lock = threading.Lock()


def _get_reader():
    global _reader, _reader_loaded
    if not _reader_loaded:
        with _lock:
            if not _reader_loaded:
                cfg = read_model_config_from_db(_DB_PATH, "ocr")
                if cfg and cfg.get("mode") == "remote":
                    logger.info("[ocr_queue] mode=remote — skipping local OCR engine load")
                    _reader_loaded = True
                    return None
                logger.info("[ocr_queue] Loading OCR engine: EasyOCR")
                from src.ai.ocr import EasyOCRReader
                _reader = EasyOCRReader.get_instance()
                _reader_loaded = True
                logger.info("[ocr_queue] OCR engine ready")
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
        if reader is None:
            save_error(task_id, "OCR engine not loaded (mode=remote)")
            return
        with _lock:
            from src.ai.ocr import extract_text_from_image
            text = extract_text_from_image(file_path)
        save_result(task_id, json.dumps({"text": text or ""}))
        logger.info(f"[ocr_queue] Completed task for {file_path} in {time.time() - start_time:.2f}s")
    except Exception as exc:
        logger.error(f"[ocr_queue] OCR failed for {file_path}: {exc}")
        save_error(task_id, str(exc))
