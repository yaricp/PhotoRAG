"""
Embedding (sentence-transformer) worker queue.

Responsibilities:
- Load the embedding model (name read from main DB at startup, downloaded from
  HuggingFace via SentenceTransformer if not cached).
- Accept tasks: encode text with purpose "save" or "search".
- Save results to task_results.db. Zero access to the main photo DB.
"""
import os
import time
import json
import threading

from huey import SqliteHuey
from loguru import logger

from src.db.task_results import save_result, save_error
from src.queues.queue_config import get_model_name_from_db, update_model_status_raw

from src.config import Database_Settings as _DB_Settings
_DB_PATH = _DB_Settings().DATABASE_PATH
_DEFAULT_MODEL_NAME = "nomic-ai/nomic-embed-text-v1.5"

embedding_queue = SqliteHuey(
    "embedding",
    filename=os.path.join(os.getcwd(), "../embedding.sqlite3")
)

_model = None
_lock = threading.Lock()


def _get_model():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from src.queues.queue_config import read_model_config_from_db
                cfg = read_model_config_from_db(_DB_PATH, "embedding")
                if cfg and cfg.get("mode") == "remote":
                    logger.info("[embedding_queue] mode=remote — skipping local model load")
                    return None
                model_name = (cfg and cfg.get("model_name")) or _DEFAULT_MODEL_NAME
                logger.info(f"[embedding_queue] Loading model: {model_name}")
                update_model_status_raw(_DB_PATH, "embedding", "loading")
                try:
                    from sentence_transformers import SentenceTransformer
                    m = SentenceTransformer(model_name, trust_remote_code=True)
                    m.max_seq_length = 512
                    m.name = model_name
                    _model = m
                    update_model_status_raw(_DB_PATH, "embedding", "ready")
                    logger.info(f"[embedding_queue] Model ready: {model_name}")
                except Exception:
                    update_model_status_raw(_DB_PATH, "embedding", "error")
                    raise
    return _model


@embedding_queue.on_startup()
def warm():
    """Load embedding model into RAM before accepting tasks (skipped in remote mode)."""
    _get_model()


@embedding_queue.task()
def warmup_embedding_model() -> None:
    """Reset and reload the embedding model — called when config changes to local."""
    global _model
    with _lock:
        _model = None
    _get_model()


@embedding_queue.task()
def call_local_embedding_model(task_id: str, text: str, purpose: str) -> None:
    """
    Encode pre-processed text into a normalised float vector.
    Any model-specific prefix (e.g. nomic instruction prefix) is applied
    by model_services.call_embedding_model before this task is dispatched.

    Result stored as JSON: list[float]
    """
    logger.info(f"[embedding_queue] task_id={task_id} purpose={purpose!r} text={text[:40]!r}")
    start_time = time.time()
    try:
        model = _get_model()
        if model is None:
            save_error(task_id, "Local embedding model not loaded (mode=remote)")
            return
        with _lock:
            embedding = model.encode(text, normalize_embeddings=True)
        save_result(task_id, json.dumps(embedding.tolist()))
        logger.info(f"[embedding_queue] task_id={task_id} done in {time.time() - start_time:.2f}s")
    except Exception as exc:
        logger.error(f"[embedding_queue] purpose={purpose!r} failed: {exc}")
        save_error(task_id, str(exc))
