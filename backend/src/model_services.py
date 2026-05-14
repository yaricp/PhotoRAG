"""
Async model gateway.

All model calls from the pipeline, API endpoints, and AI agent tools must go
through these functions. They never load a model themselves — they either:
  - Submit a Huey task to the appropriate worker process and poll task_results.db, OR
  - Make an HTTP request to a configured remote API.

Mode (local | remote) is read from ai_model_configs in the main DB, falling back to
env-var settings if the DB is unavailable.
"""
import json
import asyncio
import os
from uuid import uuid4
from loguru import logger
from httpx import AsyncClient

from src.queues.queue_config import read_model_config_from_db
from src.task_notifier import get_notifier
from src.config import (
    TaskQueue_Settings,
    CLIP_Settings,
    Embedding_Settings,
    Translation_Settings,
    Vision_Settings,
    OCR_Settings,
)

_DB_PATH = os.path.join(os.getcwd(), "../db.sqlite3")

_task_queue_settings = TaskQueue_Settings()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_mode(model_type: str, fallback_settings) -> str:
    cfg = read_model_config_from_db(_DB_PATH, model_type)
    if cfg and cfg.get("mode"):
        return cfg["mode"]
    return getattr(fallback_settings, f"{model_type.upper()}_MODE",
                   getattr(fallback_settings, "TRANSLATION_MODE", "local"))


async def _wait_result(task_id: str, label: str = "") -> str:
    """
    Wait for a Huey task result via the shared TaskResultNotifier.

    The notifier issues one batched SELECT per poll interval covering all
    in-flight task IDs, so the event loop is never blocked by individual
    synchronous SQLite reads.

    Raises asyncio.TimeoutError when TASK_RESULT_TIMEOUT is exceeded.
    Raises RuntimeError if the task stored an error via save_error().
    """
    tag = f"[{label}] " if label else ""
    logger.debug(f"{tag}Waiting for task {task_id}")
    raw = await get_notifier().wait_for_result(
        task_id, timeout=_task_queue_settings.TASK_RESULT_TIMEOUT
    )
    logger.debug(f"{tag}Task {task_id} result received")
    return raw


async def _call_remote(model_url: str, payload: dict,
                       files: dict = None, api_key: str = None) -> dict:
    """POST to a remote model API and return the JSON response body."""
    async with AsyncClient() as client:
        try:
            headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
            response = await client.post(
                model_url, json=payload, files=files, headers=headers, timeout=120.0
            )
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            logger.error(f"[model_services] Remote call to {model_url} failed: {exc}")
            raise


# ---------------------------------------------------------------------------
# CLIP
# ---------------------------------------------------------------------------

async def call_clip_model(file_path: str, task: str = "tags") -> list:
    """
    Call the CLIP model (local worker or remote API).

    task: "tags" | "categorize" | "encode_image"
    Returns deserialized Python list.
    """
    clip_settings = CLIP_Settings()
    mode = _get_mode("clip", clip_settings)

    if mode == "local":
        from src.queues.clip_queue import call_local_clip_model
        task_id = str(uuid4())
        logger.debug(f"[clip/{task}] New Async task {task_id} for {file_path}")
        call_local_clip_model(task_id, file_path, task)
        raw = await _wait_result(task_id, label=f"clip/{task}")
        result = json.loads(raw)
        logger.debug(f"[clip/{task}] task {task_id}: got {len(result)} results")
        return result
    else:
        result = await _call_remote(
            model_url=clip_settings.CLIP_API_URL,
            payload={"model": clip_settings.CLIP_MODEL, "task": task},
            files={"file": open(file_path, "rb")},
            api_key=clip_settings.CLIP_API_KEY,
        )
        return result.get("result", [])


# ---------------------------------------------------------------------------
# Vision
# ---------------------------------------------------------------------------

async def call_vision_model(file_path: str, prompt_key: str) -> str:
    """
    Generate text from an image (description or document detection).

    prompt_key: "describe_scene" | "is_document"
    Returns the generated text string.
    """
    vision_settings = Vision_Settings()
    mode = _get_mode("vision", vision_settings)

    if mode == "local":
        from src.queues.vision_queue import call_local_vision_model
        task_id = str(uuid4())
        logger.debug(f"[vision/{prompt_key}] Submitting Huey task {task_id} for {file_path}")
        call_local_vision_model(task_id, file_path, prompt_key)
        raw = await _wait_result(task_id, label=f"vision/{prompt_key}")
        text = json.loads(raw).get("text", "")
        logger.debug(f"[vision/{prompt_key}] task {task_id}: {len(text)} chars")
        return text
    else:
        result = await _call_remote(
            model_url=vision_settings.VISION_API_URL,
            payload={"model": vision_settings.VISION_DESCRIBER_MODEL, "prompt_key": prompt_key},
            files={"file": open(file_path, "rb")},
            api_key=vision_settings.VISION_API_KEY,
        )
        return result.get("text", "")


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------

async def call_embedding_model(text: str, purpose: str = "search") -> list[float]:
    """
    Encode text into a normalised embedding vector.

    purpose: "save" | "search"
    Returns list[float].
    """
    emb_settings = Embedding_Settings()
    mode = _get_mode("embedding", emb_settings)

    if mode == "local":
        from src.queues.embedding_queue import call_local_embedding_model
        task_id = str(uuid4())
        logger.debug(f"[embedding/{purpose}] Submitting Huey task {task_id}")
        call_local_embedding_model(task_id, text, purpose)
        raw = await _wait_result(task_id, label=f"embedding/{purpose}")
        result = json.loads(raw)
        logger.debug(f"[embedding/{purpose}] task {task_id}: vector dim={len(result)}")
        return result
    else:
        result = await _call_remote(
            model_url=emb_settings.EMBEDDING_API_URL,
            payload={
                "model": emb_settings.PHOTO_EMBEDDER_MODEL,
                "text": text,
                "purpose": purpose,
            },
            api_key=emb_settings.EMBEDDING_API_KEY,
        )
        return result.get("embedding", [])


# ---------------------------------------------------------------------------
# Translation
# ---------------------------------------------------------------------------

async def call_translation_model(text: str, backward: bool = False) -> str:
    """
    Translate text.

    backward=False: any → user language (forward)
    backward=True:  any → English (for embedding)
    Returns translated text string.
    """
    trans_settings = Translation_Settings()
    mode = _get_mode("translator", trans_settings)

    if mode == "local":
        from src.queues.translation_queue import call_local_translation_model
        task_id = str(uuid4())
        direction = "backward" if backward else "forward"
        logger.debug(f"[translation/{direction}] Submitting Huey task {task_id}")
        call_local_translation_model(task_id, text, backward)
        raw = await _wait_result(task_id, label=f"translation/{direction}")
        translation = json.loads(raw).get("translation", "")
        logger.debug(f"[translation/{direction}] task {task_id}: {len(translation)} chars")
        return translation
    else:
        result = await _call_remote(
            model_url=trans_settings.TRANSLATOR_API_URL,
            payload={
                "model": trans_settings.TRANSLATOR_MODEL,
                "text": text,
                "backward": backward,
            },
            api_key=trans_settings.TRANSLATOR_API_KEY,
        )
        return result.get("translation", "")


# ---------------------------------------------------------------------------
# OCR
# ---------------------------------------------------------------------------

async def call_ocr_model(file_path: str) -> str:
    """
    Extract text from an image file.
    Returns the extracted text (empty string if none found).
    """
    ocr_settings = OCR_Settings()
    mode = _get_mode("ocr", ocr_settings)

    if mode == "local":
        from src.queues.ocr_queue import call_local_ocr_model
        task_id = str(uuid4())
        logger.debug(f"[ocr] Submitting Huey task {task_id} for {file_path}")
        call_local_ocr_model(task_id, file_path)
        raw = await _wait_result(task_id, label="ocr")
        text = json.loads(raw).get("text", "")
        logger.debug(f"[ocr] task {task_id}: {len(text)} chars")
        return text
    else:
        result = await _call_remote(
            model_url=ocr_settings.OCR_API_URL,
            payload={"model": ocr_settings.OCR_MODEL},
            files={"file": open(file_path, "rb")},
            api_key=ocr_settings.OCR_API_KEY,
        )
        return result.get("text", "")
