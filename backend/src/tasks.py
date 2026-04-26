from src.queue import task_queue
from src.metadata import get_exif_data
from src.ai.ocr import extract_text_from_image
from src.ai.clip import ClipTagger
from src.ai.vision import QwenVisionGenerator
from src.geo import GeoEnricher
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
from src.models import Photo

@task_queue.task()
def download_models_task():
    """Bootstrap task: Models + Vocab + Default Categories."""
    db = SessionLocal()
    settings = Settings()
    try:
        update_model_status(db, "clip", "downloading")
        ClipTagger().download()
        update_model_status(db, "clip", "ready")
    except Exception:
        db.rollback()
        update_model_status(db, "clip", "error")

    defaults = ["Nature", "Architecture", "People", "Urban", "Interior", "Portrait", "Landscape", "Abstract", "Food", "Animals"]
    for cat in defaults:
        get_or_create_category(db, cat)

    try:
        update_model_status(db, "vision", "downloading")
        QwenVisionGenerator(settings).download()
        update_model_status(db, "vision", "ready")
    except Exception:
        db.rollback()
        update_model_status(db, "vision", "error")

    update_model_status(db, "embedding", "ready")
    db.close()

@task_queue.task()
def metadata_task(photo_id: int):
    """Enriches photo with EXIF and Reverse Geocoding (City, Country)."""
    db = SessionLocal()
    try:
        photo = db.query(Photo).filter(Photo.id == photo_id).first()
        if photo:
            res = get_exif_data(photo.file_path)
            photo.exif_data = {k: v for k, v in res.items() if k != "captured_at_obj"}
            if res.get("captured_at_obj"):
                photo.captured_at = res["captured_at_obj"]
            
            # Camera Enrichment
            if res.get("model") and res.get("model") != "Unknown":
                camera = get_or_create_camera(db, make="Unknown", model=res["model"])
                photo.camera_id = camera.id
            
            # Geo Enrichment (Reverse Geocoding)
            lat = res.get("gps_latitude")
            lon = res.get("gps_longitude")
            if lat is not None and lon is not None:
                enricher = GeoEnricher()
                address = enricher.reverse_geocode(lat, lon)
                update_photo_geoposition(db, photo_id, lat, lon, address)
                
            db.commit()
    finally:
        db.close()

@task_queue.task()
def auto_tag_clip_task(photo_id: int):
    db = SessionLocal()
    try:
        photo = db.query(Photo).filter(Photo.id == photo_id).first()
        if photo:
            tagger = ClipTagger()
            tags_with_scores = tagger.find_tags(photo.file_path)
            confident_tags = [ (t, s) for t, s in tags_with_scores if s > 0.5 ]
            photo.keywords = [t for t, s in confident_tags]
            for tag_name, score in confident_tags:
                add_photo_tag_with_score(db, photo_id, tag_name, score)
            db.commit()
    finally:
        db.close()

@task_queue.task()
def categorize_photo_task(photo_id: int):
    db = SessionLocal()
    try:
        photo = db.query(Photo).filter(Photo.id == photo_id).first()
        categories = get_all_categories(db)
        if photo and categories:
            tagger = ClipTagger()
            cat_results = tagger.categorize(photo.file_path, categories)
            for cat_name, score in cat_results:
                if score > 0.5:
                    add_photo_category_with_score(db, photo_id, cat_name, score)
            db.commit()
    finally:
        db.close()

@task_queue.task()
def vision_task(photo_id: int):
    db = SessionLocal()
    try:
        photo = db.query(Photo).filter(Photo.id == photo_id).first()
        if photo:
            gen = QwenVisionGenerator(Settings())
            desc = gen.describe_scene(photo.file_path)
            photo.description = desc
            db.commit()
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
    finally:
        db.close()
