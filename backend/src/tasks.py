from src.queue import task_queue
from src.metadata import get_exif_data
from src.ai.ocr import extract_text_from_image
from src.ai.registry import registry
from src.config import Settings
from src.database import SessionLocal
from src.db_service import (
    get_or_create_photo, 
    update_model_status, 
    get_or_create_camera, 
    update_photo_geoposition,
    get_or_create_keyword,
    add_photo_tag_with_score,
    get_all_categories,
    get_or_create_category,
    add_photo_category_with_score
)
from src.models import Photo, PhotoTag, PhotoCategory, Geoposition
import torch
import os

def check_and_trigger_finalization(db, photo_id: int):
    """Barrier: Checks if all parallel AI tasks are done, then triggers synthesis."""
    photo = db.query(Photo).filter(Photo.id == photo_id).first()
    if not photo:
        return

    # Check for presence of all synthesized parts
    has_metadata = photo.captured_at is not None
    has_tags = db.query(PhotoTag).filter_by(photo_id=photo_id).count() > 0
    has_categories = db.query(PhotoCategory).filter_by(photo_id=photo_id).count() > 0
    has_description = photo.description is not None

    if has_metadata and has_tags and has_categories and has_description:
        final_embedding_task(photo_id)

@task_queue.task()
def final_embedding_task(photo_id: int):
    """Aggregates results and saves 768-dim vector using Warm Registry Embedder."""
    db = SessionLocal()
    try:
        photo = db.query(Photo).filter(Photo.id == photo_id).first()
        if not photo:
            return

        # 1. Gather components
        tags = [pt.tag.name for pt in photo.tags_rel]
        categories = [pc.category.name for pc in photo.categories_rel]
        main_category = categories[0] if categories else "Uncategorized"
        
        geo = db.query(Geoposition).filter_by(photo_id=photo_id).first()
        location = geo.address if geo and geo.address else "Unknown Location"

        # 2. Format Synthesis Template
        photo_text = f"""
Scene: {photo.description}
Tags: {", ".join(tags)}
Category: {main_category}
Location: {location}
"""
        # 3. Generate Embedding (Using Warm Registry)
        model = registry.nomic_embedder
        embedding = model.encode(photo_text)
        
        # 4. Persist to pgvector column
        photo.embedding = embedding.tolist()
        db.commit()
    finally:
        db.close()

@task_queue.task()
def download_models_task():
    """Bootstrap task: Warm up all models in the Global Registry."""
    db = SessionLocal()
    settings = Settings()
    
    # 1. CLIP & Vocab
    try:
        update_model_status(db, "clip", "downloading")
        _ = registry.clip_tagger # Force warm-up
        update_model_status(db, "clip", "ready")
    except Exception:
        db.rollback()
        update_model_status(db, "clip", "error")

    # 2. Categories Seeding
    defaults = ["Nature", "Architecture", "People", "Urban", "Interior", "Portrait", "Landscape", "Abstract", "Food", "Animals"]
    for cat in defaults:
        get_or_create_category(db, cat)

    # 3. Vision Model (Qwen)
    try:
        update_model_status(db, "vision", "downloading")
        _ = registry.vision_generator # Force warm-up
        update_model_status(db, "vision", "ready")
    except Exception:
        db.rollback()
        update_model_status(db, "vision", "error")

    # 4. Nomic Embedder
    try:
        update_model_status(db, "embedding", "downloading")
        _ = registry.nomic_embedder # Force warm-up
        update_model_status(db, "embedding", "ready")
    except Exception:
        db.rollback()
        update_model_status(db, "embedding", "error")

    db.close()

@task_queue.task()
def metadata_task(photo_id: int):
    db = SessionLocal()
    try:
        photo = db.query(Photo).filter(Photo.id == photo_id).first()
        if photo:
            res = get_exif_data(photo.file_path)
            photo.exif_data = {k: v for k, v in res.items() if k != "captured_at_obj"}
            if res.get("captured_at_obj"):
                photo.captured_at = res["captured_at_obj"]
            
            if res.get("model") and res.get("model") != "Unknown":
                camera = get_or_create_camera(db, make="Unknown", model=res["model"])
                photo.camera_id = camera.id
            
            lat = res.get("gps_latitude")
            lon = res.get("gps_longitude")
            if lat is not None and lon is not None:
                enricher = registry.geo_enricher # Use registry for geo too
                address = enricher.reverse_geocode(lat, lon)
                update_photo_geoposition(db, photo_id, lat, lon, address)
                
            db.commit()
            check_and_trigger_finalization(db, photo_id)
    finally:
        db.close()

@task_queue.task()
def auto_tag_clip_task(photo_id: int):
    db = SessionLocal()
    try:
        photo = db.query(Photo).filter(Photo.id == photo_id).first()
        if photo:
            tagger = registry.clip_tagger
            tags_with_scores = tagger.find_tags(photo.file_path)
            confident_tags = [ (t, s) for t, s in tags_with_scores if s > 0.5 ]
            photo.keywords = [t for t, s in confident_tags]
            for tag_name, score in confident_tags:
                add_photo_tag_with_score(db, photo_id, tag_name, score)
            db.commit()
            check_and_trigger_finalization(db, photo_id)
    finally:
        db.close()

@task_queue.task()
def categorize_photo_task(photo_id: int):
    db = SessionLocal()
    try:
        photo = db.query(Photo).filter(Photo.id == photo_id).first()
        categories = get_all_categories(db)
        if photo and categories:
            tagger = registry.clip_tagger
            cat_results = tagger.categorize(photo.file_path, categories)
            for cat_name, score in cat_results:
                if score > 0.5:
                    add_photo_category_with_score(db, photo_id, cat_name, score)
            db.commit()
            check_and_trigger_finalization(db, photo_id)
    finally:
        db.close()

@task_queue.task()
def vision_task(photo_id: int):
    db = SessionLocal()
    try:
        photo = db.query(Photo).filter(Photo.id == photo_id).first()
        if photo:
            generator = registry.vision_generator
            desc = generator.describe_scene(photo.file_path)
            photo.description = desc
            db.commit()
            check_and_trigger_finalization(db, photo_id)
    finally:
        db.close()

@task_queue.task()
def ocr_task(photo_id: int):
    db = SessionLocal()
    try:
        photo = db.query(Photo).filter(Photo.id == photo_id).first()
        if photo:
            text = extract_text_from_image(photo.file_path)
            photo.ocr_text = text
            db.commit()
            
            # TRIGGER DOCUMENT DETECTION if text exists
            if text and len(text.strip()) > 0:
                is_this_document_task(photo_id)
    finally:
        db.close()

@task_queue.task()
def is_this_document_task(photo_id: int):
    """Refined check: Use Vision model to confirm if photo is a document."""
    db = SessionLocal()
    try:
        photo = db.query(Photo).filter(Photo.id == photo_id).first()
        if photo:
            gen = registry.vision_generator
            result = gen.generate_vision_text(photo.file_path, prompt_key="is_document")
            # Simple binary conversion
            photo.is_doc = "yes" in result.lower()
            db.commit()
    finally:
        db.close()
