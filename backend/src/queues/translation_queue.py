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
from src.queues.queue_config import read_model_config_from_db, update_model_status_raw

from src.config import Database_Settings as _DB_Settings
_DB_PATH = _DB_Settings().DATABASE_PATH
_DEFAULT_MODEL_NAME = "facebook/nllb-200-distilled-600M"

translation_queue = SqliteHuey(
    "translation",
    filename=os.path.join(os.getcwd(), "../translation.sqlite3")
)

_model = None
_model_loaded = False
_lock = threading.Lock()


def _get_model():
    global _model, _model_loaded
    if not _model_loaded:
        with _lock:
            if not _model_loaded:
                cfg = read_model_config_from_db(_DB_PATH, "translator")
                if cfg and cfg.get("mode") == "remote":
                    logger.info("[translation_queue] mode=remote — skipping local model load")
                    _model_loaded = True
                    return None
                model_name = (cfg and cfg.get("model_name")) or _DEFAULT_MODEL_NAME
                logger.info(f"[translation_queue] Loading model: {model_name}")
                update_model_status_raw(_DB_PATH, "translator", "loading")
                try:
                    from src.ai.translator import Translator
                    translator = Translator()
                    _model = translator
                    _model_loaded = True
                    update_model_status_raw(_DB_PATH, "translator", "ready")
                    logger.info(f"[translation_queue] Model ready: {model_name}")
                except Exception:
                    update_model_status_raw(_DB_PATH, "translator", "error")
                    raise
    return _model


@translation_queue.on_startup()
def warm():
    """Load translation model into RAM before accepting tasks."""
    _get_model()


@translation_queue.task()
def warmup_translation_model() -> None:
    """Reset and reload the translation model — called when config changes to local."""
    global _model, _model_loaded
    with _lock:
        _model = None
        _model_loaded = False
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
        if model is None:
            save_error(task_id, "translation model not loaded (mode=remote)")
            return
        with _lock:
            translation = model.translate(text=text, backward=backward)
        save_result(task_id, json.dumps({"translation": translation}))
        logger.info(f"[translation_queue] task_id={task_id} backward={backward} Translation completed in {time.time() - start_time:.2f}s")
    except Exception as exc:
        logger.error(f"[translation_queue] backward={backward} failed: {exc}")
        save_error(task_id, str(exc))
