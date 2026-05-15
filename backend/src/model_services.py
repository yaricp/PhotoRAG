"""
Async model gateway.

All model calls from the pipeline, API endpoints, and AI agent tools must go
through these functions. They never load a model themselves — they either:
  - Submit a Huey task to the appropriate worker process and poll task_results.db, OR
  - Call a provider API via LangChain (vision, OCR, translation, CLIP, embedding).

Mode (local | remote) is read from ai_model_configs in the main DB, falling back to
env-var settings if the DB is unavailable.
"""
import base64
import json
import asyncio
from uuid import uuid4
from loguru import logger

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

from src.config import Database_Settings as _DB_Settings
_DB_PATH = _DB_Settings().DATABASE_PATH

_task_queue_settings = TaskQueue_Settings()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Shared image helpers
# ---------------------------------------------------------------------------

def _encode_image_base64(file_path: str) -> str:
    """Read an image file and return its base64-encoded content."""
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _build_langchain_vision_model(
    provider: str | None,
    model_name: str,
    api_key: str | None,
    api_url: str | None,
):
    """Return a LangChain chat model that accepts multimodal (image) messages."""
    p = (provider or "").lower()

    if p == "ollama":
        from langchain_ollama import ChatOllama
        kwargs: dict = {"model": model_name}
        if api_url:
            kwargs["base_url"] = api_url
        return ChatOllama(**kwargs)

    if p == "anthropic":
        from langchain_anthropic import ChatAnthropic
        kwargs = {"model": model_name}
        if api_key:
            kwargs["api_key"] = api_key
        return ChatAnthropic(**kwargs)

    if p in ("google_genai", "google"):
        from langchain_google_genai import ChatGoogleGenerativeAI
        kwargs = {"model": model_name}
        if api_key:
            kwargs["google_api_key"] = api_key
        return ChatGoogleGenerativeAI(**kwargs)

    # Default: OpenAI-compatible
    from langchain_openai import ChatOpenAI
    kwargs = {"model": model_name}
    if api_key:
        kwargs["api_key"] = api_key
    if api_url:
        kwargs["base_url"] = api_url
    return ChatOpenAI(**kwargs)


async def _call_remote_vision(cfg: dict, file_path: str, prompt_text: str) -> str:
    """Call a remote vision-capable LLM with an image and a text prompt."""
    from langchain_core.messages import HumanMessage

    provider = cfg.get("model_provider")
    model_name = cfg.get("model_name", "gpt-4o")
    api_key = cfg.get("api_key")
    api_url = cfg.get("url")

    image_b64 = _encode_image_base64(file_path)
    llm = _build_langchain_vision_model(provider, model_name, api_key, api_url)
    msg = HumanMessage(content=[
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
        {"type": "text", "text": prompt_text},
    ])
    loop = asyncio.get_running_loop()
    logger.debug(f"[vision/remote] Sending image to remote model {model_name} at {api_url or 'default endpoint'}")
    response = await loop.run_in_executor(None, llm.invoke, [msg])
    logger.debug(f"[vision/remote] Received response from remote model: {response}")
    return response.content


# ---------------------------------------------------------------------------
# CLIP
# ---------------------------------------------------------------------------

def _load_clip_names(path: str) -> list[str]:
    """Load tag/category names from a JSON file, returning [] if unavailable."""
    import json as _json
    try:
        with open(path) as f:
            return _json.load(f)
    except Exception:
        return []


async def _call_remote_clip(cfg: dict, file_path: str, task: str) -> list:
    """Run remote CLIP tagging via a vision LLM."""
    from src.ai.clip_remote import RemoteClipTagger

    provider = cfg.get("model_provider")
    model_name = cfg.get("model_name", "gpt-4o")
    api_key = cfg.get("api_key")
    api_url = cfg.get("url")

    llm = _build_langchain_vision_model(provider, model_name, api_key, api_url)

    clip_cfg = CLIP_Settings()
    all_tags = _load_clip_names(clip_cfg.TAGS_NAMES_PATH)
    all_categories = _load_clip_names(clip_cfg.CATEGORIES_NAMES_PATH)

    tagger = RemoteClipTagger(llm=llm, all_tags=all_tags, all_categories=all_categories)

    loop = asyncio.get_running_loop()
    logger.debug(f"[clip/remote] Running remote CLIP tagger for task '{task}' on model '{model_name}' at {api_url or 'default endpoint'}")  
    if task == "tags":
        result = await loop.run_in_executor(None, tagger.get_tags, file_path)
        logger.debug(f"[clip/remote] result: {result}")
        logger.debug(f"[clip/remote] task '{task}' completed successfully") 
        return result
    elif task == "categorize":
        result = await loop.run_in_executor(None, tagger.get_categories, file_path)
        logger.debug(f"[clip/remote] result: {result}")
        logger.debug(f"[clip/remote] task '{task}' completed successfully")
        return result
    else:
        logger.warning(f"[clip/remote] Unknown task '{task}', returning []")
        return []


async def call_clip_model(file_path: str, task: str = "tags") -> list:
    """
    Call the CLIP model (local worker or remote vision-LLM tagger).

    task: "tags" | "categorize" | "encode_image"
    Returns deserialized Python list.
    """
    clip_settings = CLIP_Settings()
    cfg = read_model_config_from_db(_DB_PATH, "clip")
    mode = cfg["mode"] if cfg and cfg.get("mode") else clip_settings.CLIP_MODE

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
        return await _call_remote_clip(cfg or {}, file_path, task)


# ---------------------------------------------------------------------------
# Vision
# ---------------------------------------------------------------------------

async def call_vision_model(file_path: str, prompt_key: str) -> str:
    """
    Generate text from an image (description or document detection).

    prompt_key: "describe_scene" | "is_document"
    Returns the generated text string.
    """
    from src.ai.prompts import PROMPTS

    vision_settings = Vision_Settings()
    cfg = read_model_config_from_db(_DB_PATH, "vision")
    mode = cfg["mode"] if cfg and cfg.get("mode") else vision_settings.VISION_MODE

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
        prompt_text = PROMPTS["vision_analysis"].get(
            prompt_key, PROMPTS["vision_analysis"]["describe_scene"]
        )
        return await _call_remote_vision(cfg or {}, file_path, prompt_text)


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------

def _apply_embedding_prefix(text: str, model_name: str, purpose: str) -> str:
    """Apply model-specific text prefix before encoding.
    Currently only nomic models use instruction prefixes."""
    if "nomic" in model_name.lower():
        if purpose == "save":
            return f"search_document: {text}"
        if purpose == "search":
            return f"search_query: {text}"
    return text


async def call_embedding_model(text: str, purpose: str = "search") -> list[float]:
    """
    Encode text into a normalised embedding vector.

    purpose: "save" | "search"
    Returns list[float].
    """
    emb_settings = Embedding_Settings()
    cfg = read_model_config_from_db(_DB_PATH, "embedding")
    mode = cfg["mode"] if cfg and cfg.get("mode") else getattr(emb_settings, "EMBEDDING_MODE", "local")
    model_name = (cfg and cfg.get("model_name")) or emb_settings.PHOTO_EMBEDDER_MODEL

    # Apply model-specific prefix once, before dispatching to either path
    text = _apply_embedding_prefix(text, model_name, purpose)

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
        return await _call_remote_embedding(text, purpose, cfg, emb_settings)


async def _call_remote_embedding(
    text: str, purpose: str, cfg: dict | None, emb_settings
) -> list[float]:
    """Encode text using a LangChain embedding provider. Text arrives pre-prefixed."""
    model_name = (cfg and cfg.get("model_name")) or emb_settings.PHOTO_EMBEDDER_MODEL
    api_key = (cfg and cfg.get("api_key")) or getattr(emb_settings, "EMBEDDING_API_KEY", None)
    api_url = (cfg and cfg.get("url")) or getattr(emb_settings, "EMBEDDING_API_URL", None)
    provider = (cfg and cfg.get("model_provider")) or None

    embedder = _build_langchain_embedder(provider, model_name, api_key, api_url)
    loop = asyncio.get_running_loop()
    vector = await loop.run_in_executor(None, embedder.embed_query, text)
    logger.debug(f"[embedding/{purpose}] remote vector dim={len(vector)}")
    return vector


def _build_langchain_embedder(provider: str | None, model_name: str,
                               api_key: str | None, api_url: str | None):
    """Return the appropriate LangChain Embeddings object for the given provider."""
    p = (provider or "").lower()

    if p == "ollama":
        from langchain_ollama import OllamaEmbeddings
        kwargs = {"model": model_name}
        if api_url:
            kwargs["base_url"] = api_url
        return OllamaEmbeddings(**kwargs)

    if p in ("google_genai", "google"):
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        kwargs = {"model": model_name}
        if api_key:
            kwargs["google_api_key"] = api_key
        return GoogleGenerativeAIEmbeddings(**kwargs)

    if p == "anthropic":
        raise RuntimeError("Anthropic does not provide an embeddings API. Use a different provider.")

    # Default: OpenAI-compatible (openai, together, groq, mistral, custom OpenAI-compat endpoints)
    from langchain_openai import OpenAIEmbeddings
    kwargs = {"model": model_name}
    if api_key:
        kwargs["api_key"] = api_key
    if api_url:
        kwargs["base_url"] = api_url
    return OpenAIEmbeddings(**kwargs)


# ---------------------------------------------------------------------------
# Translation
# ---------------------------------------------------------------------------

async def _call_remote_translation(cfg: dict, text: str, *, backward: bool = False) -> str:
    """Translate text via a LangChain chat model or specialty service (DeepL, LibreTranslate)."""
    from src.ai.translator_remote import RemoteTranslator
    from src.config import Main_Settings

    main = Main_Settings()
    provider = cfg.get("model_provider")
    model_name = cfg.get("model_name")
    api_key = cfg.get("api_key")
    api_url = cfg.get("url")

    lang = main.DEFAULT_LANGUAGE
    if lang == "en":
        src_lang, tgt_lang = "Russian", "English"
    else:
        src_lang, tgt_lang = "English", "Russian"

    p = (provider or "").lower()
    if p in ("deepl", "libretranslate"):
        translator = RemoteTranslator(
            provider=p, api_key=api_key, api_url=api_url,
            src_lang=src_lang, tgt_lang=tgt_lang,
        )
    else:
        llm = _build_langchain_vision_model(provider, model_name or "gpt-4o-mini", api_key, api_url)
        translator = RemoteTranslator(llm=llm, src_lang=src_lang, tgt_lang=tgt_lang)

    loop = asyncio.get_running_loop()
    logger.debug(f"[translation/remote] Translating text with provider '{provider or 'LLM'}' and model '{model_name or 'default'}'")
    result = await loop.run_in_executor(None, translator.translate, text, backward)
    logger.debug(f"[translation/remote] Translation result: {result[:60]}{'...' if len(result) > 60 else ''}")  
    return result


async def call_translation_model(text: str, backward: bool = False) -> str:
    """
    Translate text.

    backward=False: any → user language (forward)
    backward=True:  any → English (for embedding)
    Returns translated text string.
    """
    trans_settings = Translation_Settings()
    cfg = read_model_config_from_db(_DB_PATH, "translator")
    mode = cfg["mode"] if cfg and cfg.get("mode") else trans_settings.TRANSLATOR_MODE

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
        return await _call_remote_translation(cfg or {}, text, backward=backward)


# ---------------------------------------------------------------------------
# OCR
# ---------------------------------------------------------------------------

async def _call_remote_ocr(cfg: dict, file_path: str) -> str:
    """Extract text from an image using a remote vision LLM."""
    from src.ai.ocr_remote import RemoteOCR

    provider = cfg.get("model_provider")
    model_name = cfg.get("model_name", "gpt-4o")
    api_key = cfg.get("api_key")
    api_url = cfg.get("url")

    llm = _build_langchain_vision_model(provider, model_name, api_key, api_url)
    ocr = RemoteOCR(llm)
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, ocr.extract_text, file_path)


async def call_ocr_model(file_path: str) -> str:
    """
    Extract text from an image file.
    Returns the extracted text (empty string if none found).
    """
    ocr_settings = OCR_Settings()
    cfg = read_model_config_from_db(_DB_PATH, "ocr")
    mode = cfg["mode"] if cfg and cfg.get("mode") else ocr_settings.OCR_MODE

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
        return await _call_remote_ocr(cfg or {}, file_path)
