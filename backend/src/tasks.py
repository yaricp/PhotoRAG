from src.queue import task_queue
from src.metadata import get_exif_data
from src.ai.ocr import extract_text_from_image
from src.ai.clip import ClipTagger
from src.ai.vision import QwenVisionGenerator
from src.config import Settings
from src.database import SessionLocal
from src.db_service import get_or_create_photo, update_model_status
from src.models import Photo

@task_queue.task()
def download_models_task():
    """Bootstrap task to ensure all AI models are downloaded and ready."""
    db = SessionLocal()
    settings = Settings()
    
    try:
        # 1. CLIP
        update_model_status(db, "clip", "downloading")
        ClipTagger().download()
        update_model_status(db, "clip", "ready")
    except Exception as e:
        db.rollback()
        update_model_status(db, "clip", "error")

    try:
        # 2. Vision
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
            if res.get("captured_at_obj"):
                photo.captured_at = res["captured_at_obj"]
            exif_blob = res.copy()
            exif_blob.pop("captured_at_obj", None)
            photo.exif_data = exif_blob
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
            photo.keywords = keywords
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
