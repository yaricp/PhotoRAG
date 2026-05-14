"""
Background recompute tasks — triggered after any template_tags or
template_categories change via the API.  Each task runs in a daemon thread
so the HTTP response returns immediately.

Status is tracked via ModelState:
  "clip_tags"       → "recomputing" | "ready" | "error"
  "clip_categories" → "recomputing" | "ready" | "error"
"""
from threading import Thread
from loguru import logger


def trigger_recompute_tags() -> None:
    Thread(target=_do_recompute_tags, daemon=True, name="recompute-tags").start()


def _do_recompute_tags() -> None:
    from src.db.database import SessionLocal
    from src.db_service import update_model_status
    from src.ai.clip import ClipTagger
    from src.install import _compute_model_hash, _save_hash
    from src.config import CLIP_Settings

    db = SessionLocal()
    try:
        update_model_status(db, "clip_tags", "recomputing")
        cfg = CLIP_Settings()
        tagger = ClipTagger()
        tagger.load_model()
        tagger.compute_embeddings_tags_from_db(db)
        model_hash = _compute_model_hash(cfg.CLIP_MODEL, cfg.PRETRAINED)
        _save_hash(cfg.TAGS_MODEL_HASH_PATH, model_hash)
        update_model_status(db, "clip_tags", "ready")
        logger.info("[recompute] tags.npy updated ✓")
    except Exception as e:
        logger.error(f"[recompute] tags failed: {e}")
        from src.db.database import SessionLocal as SL
        db2 = SL()
        try:
            update_model_status(db2, "clip_tags", "error")
        finally:
            db2.close()
    finally:
        db.close()


def trigger_recompute_categories() -> None:
    Thread(target=_do_recompute_categories, daemon=True, name="recompute-categories").start()


def _do_recompute_categories() -> None:
    from src.db.database import SessionLocal
    from src.db_service import update_model_status
    from src.ai.clip import ClipTagger
    from src.install import _compute_model_hash, _save_hash
    from src.config import CLIP_Settings

    db = SessionLocal()
    try:
        update_model_status(db, "clip_categories", "recomputing")
        cfg = CLIP_Settings()
        tagger = ClipTagger()
        tagger.load_model()
        tagger.compute_embeddings_categories_from_db(db)
        model_hash = _compute_model_hash(cfg.CLIP_MODEL, cfg.PRETRAINED)
        _save_hash(cfg.CATEGORIES_MODEL_HASH_PATH, model_hash)
        update_model_status(db, "clip_categories", "ready")
        logger.info("[recompute] categories.npy updated ✓")
    except Exception as e:
        logger.error(f"[recompute] categories failed: {e}")
        from src.db.database import SessionLocal as SL
        db2 = SL()
        try:
            update_model_status(db2, "clip_categories", "error")
        finally:
            db2.close()
    finally:
        db.close()
