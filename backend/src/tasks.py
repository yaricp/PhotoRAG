from src.queue import task_queue
from src.metadata import get_exif_data
from src.ai.ocr import extract_text_from_image
from src.ai.clip import ClipTagger
from src.ai.vision import QwenVisionGenerator
from src.config import Settings
from src.database import SessionLocal
from src.db_service import (
    get_or_create_photo, 
    update_model_status, 
    get_or_create_camera, 
    update_photo_geoposition,
    get_or_create_keyword
)
from src.models import Photo

@task_queue.task()
def download_models_task():
    """Bootstrap task to ensure all AI models are downloaded and ready."""
    db = SessionLocal()
    settings = Settings()
    try:
        update_model_status(db, "clip", "downloading")
        ClipTagger().download()
        update_model_status(db, "clip", "ready")
    except Exception as e:
        db.rollback()
        update_model_status(db, "clip", "error")

    try:
        update_model_status(db, "vision", "downloading")
        QwenVisionGenerator(settings).download()
        update_model_status(db, "vision", "ready")
    except Exception as e:
        db.rollback()
        update_model_status(db, "vision", "error")

    update_model_status(db, "embedding", "ready")
    db.close()

@task_queue.task()
def metadata_task(photo_id: int):
    db = SessionLocal()
    try:
        photo = db.query(Photo).filter(Photo.id == photo_id).first()
        if photo:
            res = get_exif_data(photo.file_path)
            # 1. Update existing JSON blob
            photo.exif_data = {k: v for k, v in res.items() if k != "captured_at_obj"}
            
            # 2. Update specific columns
            if res.get("captured_at_obj"):
                photo.captured_at = res["captured_at_obj"]
            
            # 3. Relational: Camera
            if res.get("model") and res.get("model") != "Unknown":
                camera = get_or_create_camera(db, make="Unknown", model=res["model"])
                photo.camera_id = camera.id
            
            # 4. Relational: Geoposition
            lat = res.get("gps_lat")
            lon = res.get("gps_lon")
            # Simple check if lat/lon are valid floats (need better parsing in real case)
            try:
                if lat and lon and lat != "None" and lon != "None":
                    # Placeholder for coordinate parsing
                    update_photo_geoposition(db, photo_id, float(0.0), float(0.0)) 
            except Exception:
                pass

            db.commit()
    finally:
        db.close()

@task_queue.task()
def clip_task(photo_id: int):
    db = SessionLocal()
    try:
        photo = db.query(Photo).filter(Photo.id == photo_id).first()
        if photo:
            tagger = ClipTagger()
            keywords = tagger.generate_keywords(photo.file_path)
            
            # 1. Update JSON blob
            photo.keywords = keywords
            
            # 2. Relational: Keywords
            for kw_name in keywords:
                kw_obj = get_or_create_keyword(db, kw_name)
                if kw_obj not in photo.keywords_rel:
                    photo.keywords_rel.append(kw_obj)
            
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
