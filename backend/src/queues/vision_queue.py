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
from src.queues.queue_config import read_model_config_from_db, update_model_status_raw

from src.config import Database_Settings as _DB_Settings
_DB_PATH = _DB_Settings().DATABASE_PATH
_DEFAULT_MODEL_NAME = "Qwen/Qwen2-VL-2B-Instruct"

vision_queue = SqliteHuey(
    "vision",
    filename=os.path.join(os.environ.get("QUEUE_DB_DIR", os.path.join(os.getcwd(), "..")), "vision.sqlite3")
)

_model = None
_model_loaded = False
_lock = threading.Lock()


def _get_model():
    global _model, _model_loaded
    if not _model_loaded:
        with _lock:
            if not _model_loaded:
                cfg = read_model_config_from_db(_DB_PATH, "vision")
                if cfg and cfg.get("mode") == "remote":
                    logger.info("[vision_queue] mode=remote — skipping local model load")
                    _model_loaded = True
                    return None
                model_name = (cfg and cfg.get("model_name")) or _DEFAULT_MODEL_NAME
                logger.info(f"[vision_queue] Loading model: {model_name}")
                update_model_status_raw(_DB_PATH, "vision", "loading")
                try:
                    from src.ai.vision import QwenVisionGenerator
                    generator = QwenVisionGenerator()
                    _model = generator
                    _model_loaded = True
                    update_model_status_raw(_DB_PATH, "vision", "ready")
                    logger.info(f"[vision_queue] Model ready: {model_name}")
                except Exception:
                    update_model_status_raw(_DB_PATH, "vision", "error")
                    raise
    return _model


@vision_queue.on_startup()
def warm():
    """Load vision model weights into RAM before accepting tasks."""
    generator = _get_model()
    if generator is not None:
        generator.load()  # actually loads weights; no-op if already loaded


@vision_queue.task()
def warmup_vision_model() -> None:
    """Reset and reload the vision model — called when config changes to local."""
    global _model, _model_loaded
    with _lock:
        _model = None
        _model_loaded = False
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
        if model is None:
            save_error(task_id, "vision model not loaded (mode=remote)")
            return
        with _lock:
            text = model.generate_vision_text(file_path=file_path, prompt_key=prompt_key)
        save_result(task_id, json.dumps({"text": text}))
        logger.info(f"[vision_queue] Completed task: {prompt_key} for {file_path} in {time.time() - start_time:.2f}s")
    except Exception as exc:
        logger.error(f"[vision_queue] prompt_key={prompt_key!r} failed for {file_path}: {exc}")
        save_error(task_id, str(exc))
