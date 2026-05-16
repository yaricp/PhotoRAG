"""
CLIP worker queue.

Responsibilities:
- Load the CLIP model (name read from main DB at startup, downloaded from HuggingFace
  / open_clip if not cached).
- Accept tasks: tags, categorize, encode_image.
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
_DEFAULT_MODEL_NAME = "ViT-B-32"

clip_queue = SqliteHuey(
    "clip",
    filename=os.path.join(os.environ.get("QUEUE_DB_DIR", os.path.join(os.getcwd(), "..")), "clip.sqlite3")
)

_model = None
_model_loaded = False
_lock = threading.Lock()


def _get_model():
    global _model, _model_loaded
    if not _model_loaded:
        with _lock:
            if not _model_loaded:
                cfg = read_model_config_from_db(_DB_PATH, "clip")
                if cfg and cfg.get("mode") == "remote":
                    logger.info("[clip_queue] mode=remote — skipping local model load")
                    _model_loaded = True
                    return None
                model_name = (cfg and cfg.get("model_name")) or _DEFAULT_MODEL_NAME
                logger.info(f"[clip_queue] Loading model: {model_name}")
                update_model_status_raw(_DB_PATH, "clip", "loading")
                try:
                    from src.ai.clip import ClipTagger
                    tagger = ClipTagger()
                    tagger.load_model()
                    tagger.load_tags()
                    tagger.load_or_compute_categories()
                    _model = tagger
                    _model_loaded = True
                    update_model_status_raw(_DB_PATH, "clip", "ready")
                    logger.info(f"[clip_queue] Model ready: {model_name}")
                except Exception:
                    update_model_status_raw(_DB_PATH, "clip", "error")
                    raise
    return _model


@clip_queue.on_startup()
def warm():
    """Load model into RAM before the worker accepts any tasks."""
    _get_model()


@clip_queue.task()
def warmup_clip_model() -> None:
    """Reset and reload the CLIP model — called when config changes to local."""
    global _model, _model_loaded
    with _lock:
        _model = None
        _model_loaded = False
    _get_model()


@clip_queue.task()
def call_local_clip_model(task_id: str, file_path: str, task: str = "tags") -> None:
    """
    Run CLIP inference and store the JSON-encoded result in task_results.db.

    task:
      "tags"         -> list[list[str, float]]  (tag_name, score pairs)
      "categorize"   -> list[list[str, float]]  (category_name, score pairs)
      "encode_image" -> list[float]             (normalised image feature vector)
    """
    logger.info(f"[clip_queue] Received task: {task} for {file_path}")
    start_time = time.time()
    try:
        model = _get_model()
        if model is None:
            save_error(task_id, "CLIP model not loaded (mode=remote)")
            return
        with _lock:
            if task == "tags":
                result = model.find_tags(file_path)
            elif task == "categorize":
                result = model.categorize(file_path)
            elif task == "encode_image":
                result = model.encode_image(file_path)
            else:
                raise ValueError(f"[clip_queue] Unknown task: {task!r}")
        logger.info(f"[clip_queue] CLIP task {task} for {file_path} result: {result}")
        logger.info(f"[clip_queue] Saving result for task_id={task_id}")
        save_result(task_id, json.dumps(result))
        logger.info(f"[clip_queue] Completed task: {task} for {file_path} in {time.time() - start_time:.2f}s")
    except Exception as exc:
        logger.error(f"[clip_queue] task={task!r} failed for {file_path}: {exc}")
        save_error(task_id, str(exc))
