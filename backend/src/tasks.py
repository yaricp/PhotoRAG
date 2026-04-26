from src.queue import task_queue
from src.metadata import get_exif_data
from src.ai.ocr import extract_text_from_image
from src.ai.clip import ClipTagger
from src.ai.vision import QwenVisionGenerator
from src.config import Settings
from src.database import SessionLocal
from src.models import Photo

@task_queue.task()
def metadata_task(photo_id: int):
    db = SessionLocal()
    try:
        photo = db.query(Photo).filter(Photo.id == photo_id).first()
        if photo:
            exif = get_exif_data(photo.file_path)
            photo.exif_data = exif
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
