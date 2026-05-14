"""
Translation worker queue.

Responsibilities:
- Load the translation model (name read from main DB at startup, downloaded from
  HuggingFace if not cached).
- Accept tasks: translate text forward (EN → user language) or backward (any → EN).
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
_DEFAULT_MODEL_NAME = "facebook/nllb-200-distilled-600M"

translation_queue = SqliteHuey(
    "translation",
    filename=os.path.join(os.getcwd(), "../translation.sqlite3")
)

_model = None
_lock = threading.Lock()


def _get_model():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                model_name = get_model_name_from_db(_DB_PATH, "translator", _DEFAULT_MODEL_NAME)
                logger.info(f"[translation_queue] Loading model: {model_name}")
                from src.ai.translator import Translator
                translator = Translator()
                _model = translator
                logger.info(f"[translation_queue] Model ready: {model_name}")
    return _model


@translation_queue.on_startup()
def warm():
    """Load translation model into RAM before accepting tasks."""
    _get_model()


@translation_queue.task()
def call_local_translation_model(task_id: str, text: str, backward: bool = False) -> None:
    """
    Translate text and store the result in task_results.db.

    backward=False: any language → user's DEFAULT_LANGUAGE (forward)
    backward=True:  any language → English (backward, for embedding)

    Result stored as JSON: {"translation": "<translated text>"}
    """
    logger.info(f"[translation_queue] task_id={task_id} backward={backward} Translating text: {text[:30]}...")
    start_time = time.time()
    try:
        model = _get_model()
        with _lock:
            translation = model.translate(text=text, backward=backward)
        save_result(task_id, json.dumps({"translation": translation}))
        logger.info(f"[translation_queue] task_id={task_id} backward={backward} Translation completed in {time.time() - start_time:.2f}s")
    except Exception as exc:
        logger.error(f"[translation_queue] backward={backward} failed: {exc}")
        save_error(task_id, str(exc))
