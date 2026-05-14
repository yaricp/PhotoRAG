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
from src.queues.queue_config import get_model_name_from_db

_DB_PATH = os.path.join(os.getcwd(), "../db.sqlite3")
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
                model_name = get_model_name_from_db(_DB_PATH, "embedding", _DEFAULT_MODEL_NAME)
                logger.info(f"[embedding_queue] Loading model: {model_name}")
                from sentence_transformers import SentenceTransformer
                m = SentenceTransformer(model_name, trust_remote_code=True)
                m.max_seq_length = 512
                m.name = model_name
                _model = m
                logger.info(f"[embedding_queue] Model ready: {model_name}")
    return _model


@embedding_queue.on_startup()
def warm():
    """Load embedding model into RAM before accepting tasks."""
    _get_model()


@embedding_queue.task()
def call_local_embedding_model(task_id: str, text: str, purpose: str) -> None:
    """
    Encode text into a normalised float vector.

    purpose:
      "save"   -> prepends "search_document: " (nomic convention)
      "search" -> prepends "search_query: "

    Result stored as JSON: list[float]
    """
    logger.info(f"[embedding_queue] task_id={task_id} purpose={purpose!r} Encoding text: {text[:30]}...")
    start_time = time.time()
    try:
        model = _get_model()
        if purpose == "save":
            text = f"search_document: {text}"
        elif purpose == "search":
            text = f"search_query: {text}"
        with _lock:
            embedding = model.encode(text, normalize_embeddings=True)
        save_result(task_id, json.dumps(embedding.tolist()))
        logger.info(f"[embedding_queue] task_id={task_id} purpose={purpose!r} Encoding completed in {time.time() - start_time:.2f}s")
    except Exception as exc:
        logger.error(f"[embedding_queue] purpose={purpose!r} failed: {exc}")
        save_error(task_id, str(exc))
