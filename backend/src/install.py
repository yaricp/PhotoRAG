# src/install.py
"""
Установочный пайплайн — запускается один раз синхронно перед стартом сервера.
Идемпотентен: повторный запуск безопасен, пропускает уже готовые шаги.
"""

import hashlib
import os
from typing import Optional

from loguru import logger
from sqlalchemy.orm import Session

from src.config import (
    Chat_Settings,
    CLIP_Settings,
    Embedding_Settings,
    OCR_Settings,
    Translation_Settings,
    Vision_Settings,
)


def _local_ml_models() -> list[str]:
    """Return list of model names that are configured to run locally."""
    result = []
    if Vision_Settings().VISION_MODE == "local":
        result.append("vision")
    if Embedding_Settings().EMBEDDING_MODE == "local":
        result.append("embedding")
    if Translation_Settings().TRANSLATOR_MODE == "local":
        result.append("translator")
    if OCR_Settings().OCR_MODE == "local":
        result.append("ocr")
    if Chat_Settings().CHAT_MODEL_MODE == "local":
        result.append("chat")
    return result


from sqlalchemy import text

from src.db.database import engine
from src.db_service import (
    get_all_categories,
    get_model_or_none,
    get_model_status,
    get_or_create_template_category,
    get_or_create_template_tag,
    get_setting,
    init_default_model_configs,
    seed_prompts_from_json,
    set_setting,
    update_model_status,
)
from src.models import Base, ModelState
from src.utils import load_categories_from_json

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compute_model_hash(model_name: str, pretrained: str) -> str:
    """Хеш конфига модели — инвалидирует .npy при смене модели в .env"""
    return hashlib.md5(f"{model_name}:{pretrained}".encode()).hexdigest()


def _save_hash(hash_path: str, hash_value: str) -> None:
    os.makedirs(os.path.dirname(hash_path), exist_ok=True)
    with open(hash_path, "w") as f:
        f.write(hash_value)


def _read_hash(hash_path: str) -> Optional[str]:
    if not os.path.exists(hash_path):
        return None
    with open(hash_path) as f:
        return f.read().strip()


def _remove_if_exists(*paths: str) -> None:
    for path in paths:
        if os.path.exists(path):
            os.remove(path)
            logger.debug(f"Removed stale cache: {path}")


# ---------------------------------------------------------------------------
# Cache validators
# ---------------------------------------------------------------------------


def _is_tags_cache_valid(cfg: CLIP_Settings, model_hash: str) -> bool:
    """
    tags.npy валиден если:
      1. Файл существует
      2. Хеш модели совпадает (модель не сменилась в .env)
    """
    if not os.path.exists(cfg.NPY_PATH):
        return False
    saved = _read_hash(cfg.TAGS_MODEL_HASH_PATH)
    return saved == model_hash


def _is_categories_cache_valid(cfg: CLIP_Settings, model_hash: str, db: Session) -> bool:
    """
    categories.npy валиден если:
      1. Файл существует
      2. Хеш модели совпадает (модель не сменилась в .env)
      3. Хеш содержимого категорий из БД совпадает (никто не добавил/изменил категории)
    """
    if not os.path.exists(cfg.CATEGORIES_NPY_PATH):
        return False

    # Проверка 2: модель не сменилась
    saved_model_hash = _read_hash(cfg.CATEGORIES_MODEL_HASH_PATH)
    if saved_model_hash != model_hash:
        return False

    # Проверка 3: содержимое категорий в БД не менялось
    from src.ai.clip import ClipTagger

    rows = get_all_categories(db)
    if not rows:
        return False
    categories = [{"id": c.id, "name": c.name, "prompt": c.prompt} for c in rows]
    return ClipTagger().is_cache_category_valid(categories, cfg.CATEGORIES_HASH_PATH)


# ---------------------------------------------------------------------------
# Installers
# ---------------------------------------------------------------------------


def _seed_template_tags_if_empty(db: Session) -> None:
    """
    Seed template_tags from the cached vocabulary file if the table is empty.
    Called unconditionally before install_clip so that users who already have
    a valid tags.npy (from before this feature) still get the table populated.
    """
    from src.db_service import get_all_template_tags_ordered

    if get_all_template_tags_ordered(db):
        logger.info("[template_tags] Already seeded, skipping.")
        return

    cfg = CLIP_Settings()
    if not os.path.exists(cfg.TAGS_LIST_PATH):
        logger.info("[template_tags] Vocabulary file not found — will seed after download inside install_clip.")
        return

    with open(cfg.TAGS_LIST_PATH) as f:
        tags = [line.strip() for line in f if line.strip()]

    if not tags:
        logger.info("[template_tags] Vocabulary file is empty — skipping seed.")
        return

    logger.info(f"[template_tags] Seeding {len(tags)} tags from vocabulary file...")
    for tag_name in tags:
        get_or_create_template_tag(db, tag_name, tag_name)
    db.commit()
    logger.info(f"[template_tags] Seeded {len(tags)} template_tags ✓")


def install_categories(db: Session) -> None:
    """
    Seed default_categories.json into both `categories` (legacy) and `template_categories` tables.
    Idempotent — skips if already seeded.
    """
    if get_model_status(db, "categories") == "ready":
        logger.info("[categories] Already seeded, skipping.")
        return

    logger.info("[categories] Seeding default categories...")
    base_dir = os.path.dirname(os.path.dirname(__file__))
    defaults_path = os.path.join(base_dir, "defaults", "default_categories.json")
    defaults = load_categories_from_json(defaults_path)
    for cat in defaults:
        get_or_create_template_category(db, cat["name"], cat["prompt"])
    db.commit()
    update_model_status(db, "categories", "ready")
    logger.info("[categories] Seeding done ✓")


def install_clip(db: Session) -> None:
    """
    Скачать CLIP веса + словарь + предвычислить tags.npy и categories.npy.

    Инвалидация кешей:
      - tags.npy      — при смене CLIP_MODEL / PRETRAINED в .env
      - categories.npy — при смене модели ИЛИ изменении категорий в БД
    """
    cfg = CLIP_Settings()
    model_hash = _compute_model_hash(cfg.CLIP_MODEL, cfg.PRETRAINED)

    # --- Проверяем валидность кешей ---
    tags_valid = _is_tags_cache_valid(cfg, model_hash)
    categories_valid = _is_categories_cache_valid(cfg, model_hash, db)

    if not tags_valid:
        logger.warning("[clip/tags] Cache invalid — will recompute tags.npy")
        _remove_if_exists(cfg.NPY_PATH, cfg.TAGS_MODEL_HASH_PATH)

    if not categories_valid:
        logger.warning("[clip/categories] Cache invalid — will recompute categories.npy")
        _remove_if_exists(
            cfg.CATEGORIES_NPY_PATH,
            cfg.CATEGORIES_HASH_PATH,
            cfg.CATEGORIES_MODEL_HASH_PATH,
        )

    # Ранний выход — оба кеша валидны и модель уже установлена
    if get_model_status(db, "clip") == "ready" and tags_valid and categories_valid:
        logger.info("[clip] All caches valid, skipping ✓")
        return

    import open_clip

    from src.ai.clip import ClipTagger

    tagger = ClipTagger()

    try:
        update_model_status(db, "clip", "downloading")

        # 1. Веса модели
        logger.info(f"[clip] Downloading weights: {cfg.CLIP_MODEL}/{cfg.PRETRAINED}...")
        open_clip.create_model_and_transforms(cfg.CLIP_MODEL, cfg.PRETRAINED)
        logger.info("[clip] Weights ready ✓")

        tagger.load_model()

        # 2. Теги — seed template_tags + compute embeddings
        if not tags_valid:
            if not os.path.exists(cfg.TAGS_LIST_PATH):
                logger.info("[clip/tags] Downloading Open Images vocabulary...")
                tags = tagger.download_vocabulary()
                logger.info(f"[clip/tags] Vocabulary downloaded: {len(tags)} tags ✓")
            else:
                with open(cfg.TAGS_LIST_PATH) as f:
                    tags = [line.strip() for line in f if line.strip()]
                logger.info(f"[clip/tags] Vocabulary loaded from cache: {len(tags)} tags ✓")

            # Seed template_tags table (idempotent)
            logger.info(f"[clip/tags] Seeding {len(tags)} tags into template_tags...")
            for tag_name in tags:
                get_or_create_template_tag(db, tag_name, tag_name)
            db.commit()
            logger.info("[clip/tags] template_tags seeded ✓")

            # Compute embeddings from DB to keep tags_names.json in sync
            tagger.compute_embeddings_tags_from_db(db)
            _save_hash(cfg.TAGS_MODEL_HASH_PATH, model_hash)
            logger.info("[clip/tags] tags.npy saved ✓")
        else:
            logger.info("[clip/tags] Cache valid, skipping ✓")

        # 3. Категории
        if not categories_valid:
            logger.info("[clip/categories] Computing categories embeddings...")
            tagger.compute_embeddings_categories_from_db(db)
            _save_hash(cfg.CATEGORIES_MODEL_HASH_PATH, model_hash)
            logger.info("[clip/categories] categories.npy saved ✓")
        else:
            logger.info("[clip/categories] Cache valid, skipping ✓")

        update_model_status(db, "clip", "ready")
        logger.info("[clip] Installation complete ✓")

    except Exception as e:
        update_model_status(db, "clip", "error")
        logger.error(f"[clip] Installation failed: {e}")
        raise


def install_vision(db: Session) -> None:
    """Скачать Qwen2-VL веса в HuggingFace кеш"""
    if get_model_status(db, "vision") == "ready":
        logger.info("[vision] Already ready, skipping.")
        return

    from src.ai.vision import QwenVisionGenerator

    try:
        update_model_status(db, "vision", "downloading")
        logger.info("[vision] Downloading Qwen2-VL weights (this may take a while)...")
        QwenVisionGenerator().download()
        update_model_status(db, "vision", "ready")
        logger.info("[vision] Installation complete ✓")
    except Exception as e:
        update_model_status(db, "vision", "error")
        logger.error(f"[vision] Installation failed: {e}")
        raise


def install_embedding(db: Session) -> None:
    """Скачать nomic-embed веса в HuggingFace кеш"""
    if get_model_status(db, "embedding") == "ready":
        logger.info("[embedding] Already ready, skipping.")
        return

    try:
        update_model_status(db, "embedding", "downloading")
        logger.info("[embedding] Downloading nomic-embed-text-v1.5...")
        from sentence_transformers import SentenceTransformer

        SentenceTransformer(
            Embedding_Settings().PHOTO_EMBEDDER_MODEL,
            trust_remote_code=True,
        )
        update_model_status(db, "embedding", "ready")
        logger.info("[embedding] Installation complete ✓")
    except Exception as e:
        update_model_status(db, "embedding", "error")
        logger.error(f"[embedding] Installation failed: {e}")
        raise


def install_translator(db: Session) -> None:
    """Скачать mBART weights в HuggingFace кеш"""
    if get_model_status(db, "translator") == "ready":
        logger.info("[translator] Already ready, skipping.")
        return
    try:
        update_model_status(db, "translator", "downloading")
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        translate_name_model = Translation_Settings().TRANSLATOR_MODEL
        logger.info(f"[translator] Downloading {translate_name_model}...")
        AutoModelForSeq2SeqLM.from_pretrained(translate_name_model).to(torch.float16)
        AutoTokenizer.from_pretrained(translate_name_model)
        update_model_status(db, "translator", "ready")
        logger.info("[translator] Installation complete ✓")
    except Exception as e:
        update_model_status(db, "translator", "error")
        logger.error(f"[translator] Installation failed: {e}")
        raise


def install_chat(db: Session) -> None:
    """Скачать Chat LLM веса в HuggingFace кеш"""
    if get_model_status(db, "chat") == "ready":
        logger.info("[chat] Already ready, skipping.")
        return
    try:
        update_model_status(db, "chat", "downloading")
        from transformers import AutoModelForCausalLM, AutoTokenizer

        chat_model_name = Chat_Settings().CHAT_LOCAL_MODEL
        logger.info(f"[chat] Downloading {chat_model_name} (this may take a while)...")
        AutoTokenizer.from_pretrained(chat_model_name)
        AutoModelForCausalLM.from_pretrained(chat_model_name)
        update_model_status(db, "chat", "ready")
        logger.info("[chat] Installation complete ✓")
    except Exception as e:
        update_model_status(db, "chat", "error")
        logger.error(f"[chat] Installation failed: {e}")
        raise


def install_ocr(db: Session) -> None:
    """Скачать EasyOCR веса в кеш"""
    if get_model_status(db, "ocr") == "ready":
        logger.info("[ocr] Already ready, skipping.")
        return
    try:
        update_model_status(db, "ocr", "downloading")
        from src.ai.ocr import EasyOCRReader

        logger.info("[ocr] Downloading EasyOCR models (ru+en)...")
        # Initialize singleton to trigger download
        EasyOCRReader.get_instance(languages=["en", "ru"])
        update_model_status(db, "ocr", "ready")
        logger.info("[ocr] Installation complete ✓")
    except Exception as e:
        update_model_status(db, "ocr", "error")
        logger.error(f"[ocr] Installation failed: {e}")
        raise


def init_db(db: Session):
    logger.info("[db] Creating tables...")
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(
            text("""
            CREATE VIRTUAL TABLE IF NOT EXISTS photo_embeddings_vss
            USING vec0(embedding FLOAT[768]);
        """)
        )
    ml_local_models = _local_ml_models()
    clip_local_models = CLIP_Settings().local_models
    for local_model_name in ml_local_models + clip_local_models:
        if not get_model_or_none(db, local_model_name):
            db.add(ModelState(name=local_model_name, status="pending"))

    # Initialize default model configurations
    init_default_model_configs(db)

    # Recompute status keys for template vocabularies
    for recompute_key in ("clip_tags", "clip_categories"):
        if not get_model_or_none(db, recompute_key):
            db.add(ModelState(name=recompute_key, status="ready"))

    # Seed default app settings
    if get_setting(db, "default_folder") is None:
        set_setting(db, "default_folder", "")

    db.commit()
    logger.info("[db] Tables ready ✓")


def run_install(db: Session) -> None:
    """
    Точка входа установочного пайплайна.
    Вызывается из run.py синхронно перед стартом сервера.

    Порядок важен:
      1. Категории в БД должны быть засеяны ДО install_clip,
         потому что install_clip читает их для categories.npy
    """
    local_ml = _local_ml_models()
    clip_settings = CLIP_Settings()
    local_clip = clip_settings.local_models
    local_models = local_ml + local_clip
    logger.info(f"[install] Local models: {local_models}")

    # 1. DB init
    init_db(db)

    # 1b. Seed prompts table from prompts.json (idempotent)
    from pathlib import Path

    _prompts_json = Path(__file__).parent.parent / "prompts" / "prompts.json"
    seeded = seed_prompts_from_json(db, _prompts_json)
    if seeded:
        logger.info(f"[install] Seeded {seeded} prompt(s) from prompts.json")

    # 2. Всегда — засеять категории в БД
    install_categories(db)

    # 2b. Seed template_tags from vocabulary file if table is empty
    # (runs before install_clip so existing-cache users also get the table populated)
    _seed_template_tags_if_empty(db)

    # 3. Всегда — CLIP (теги + категории .npy)
    install_clip(db)

    # 3. Vision — только если local
    if "vision" in local_models:
        install_vision(db)
    else:
        logger.info("[vision] Mode=remote, skipping download.")
        update_model_status(db, "vision", "ready")

    # 4. Embedding — только если local
    if "embedding" in local_models:
        install_embedding(db)
    else:
        logger.info("[embedding] Mode=remote, skipping download.")
        update_model_status(db, "embedding", "ready")

    # 5. Translator — только если local
    if "translator" in local_models:
        install_translator(db)
    else:
        logger.info("[translator] Mode=remote, skipping download.")
        update_model_status(db, "translator", "ready")

    # 6. OCR — только если local
    if "ocr" in local_models:
        install_ocr(db)
    else:
        logger.info("[ocr] Mode=remote, skipping download.")
        update_model_status(db, "ocr", "ready")

    # 7. Chat — только если local
    if "chat" in local_models:
        install_chat(db)
    else:
        logger.info("[chat] Mode=remote, skipping download.")
        update_model_status(db, "chat", "ready")

    logger.info("[install] All done. System ready ✓")
