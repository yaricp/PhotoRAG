from src.queue import task_queue
from src.metadata import get_exif_data
from src.ai.ocr import extract_text_from_image
from src.ai.clip import ClipTagger
from src.ai.vision import QwenVisionGenerator
from src.config import Settings
from src.database import SessionLocal
from src.db_service import get_or_create_photo

@task_queue.task()
def metadata_task(filepath: str):
    db = SessionLocal()
    try:
        photo = get_or_create_photo(db, filepath)
        exif = get_exif_data(filepath)
        photo.exif_data = exif
        db.commit()
    finally:
        db.close()

@task_queue.task()
def clip_task(filepath: str):
    db = SessionLocal()
    try:
        photo = get_or_create_photo(db, filepath)
        tagger = ClipTagger()
        keywords = tagger.generate_keywords(filepath)
        photo.keywords = keywords
        db.commit()
    finally:
        db.close()

@task_queue.task()
def vision_task(filepath: str):
    db = SessionLocal()
    try:
        photo = get_or_create_photo(db, filepath)
        gen = QwenVisionGenerator(Settings())
        desc = gen.describe_scene(filepath)
        photo.description = desc
        db.commit()
    finally:
        db.close()

@task_queue.task()
def ocr_task(filepath: str):
    db = SessionLocal()
    try:
        photo = get_or_create_photo(db, filepath)
        text = extract_text_from_image(filepath)
        photo.ocr_text = text
        db.commit()
    finally:
        db.close()
