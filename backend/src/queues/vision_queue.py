"""
Vision (LLM) worker queue.

Responsibilities:
- Load the vision model (name read from main DB at startup).
- Accept tasks: describe_scene, is_document.
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
_DEFAULT_MODEL_NAME = "Qwen/Qwen2-VL-2B-Instruct"

vision_queue = SqliteHuey(
    "vision",
    filename=os.path.join(os.getcwd(), "../vision.sqlite3")
)

_model = None
_lock = threading.Lock()


def _get_model():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                model_name = get_model_name_from_db(_DB_PATH, "vision", _DEFAULT_MODEL_NAME)
                logger.info(f"[vision_queue] Loading model: {model_name}")
                from src.ai.vision import QwenVisionGenerator
                generator = QwenVisionGenerator()
                _model = generator
                logger.info(f"[vision_queue] Model ready: {model_name}")
    return _model


@vision_queue.on_startup()
def warm():
    """Load vision model into RAM before accepting tasks."""
    _get_model()


@vision_queue.task()
def call_local_vision_model(task_id: str, file_path: str, prompt_key: str) -> None:
    """
    Generate text from an image using the vision model.

    prompt_key:
      "describe_scene" -> natural-language description of the photo
      "is_document"    -> "yes" or "no"

    Result stored as JSON: {"text": "<generated text>"}
    """
    logger.info(f"[vision_queue] Received task: {prompt_key} for {file_path}")
    start_time = time.time()
    try:
        model = _get_model()
        with _lock:
            text = model.generate_vision_text(file_path=file_path, prompt_key=prompt_key)
        save_result(task_id, json.dumps({"text": text}))
        logger.info(f"[vision_queue] Completed task: {prompt_key} for {file_path} in {time.time() - start_time:.2f}s")
    except Exception as exc:
        logger.error(f"[vision_queue] prompt_key={prompt_key!r} failed for {file_path}: {exc}")
        save_error(task_id, str(exc))
