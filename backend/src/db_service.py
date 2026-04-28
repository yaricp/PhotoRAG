from typing import Optional, List

from sqlalchemy.orm import Session
from src.models import (
    Photo, ModelState, Camera, Geoposition, 
    Keyword, Tag, Person, Category, PhotoTag, PhotoCategory,
    Watcher
)
from src.utils import generate_file_hash
from datetime import datetime
from loguru import logger

# Registration & Status Helpers (Existing)
def check_photo_hash_exists(db: Session, hash_str: str) -> Photo:
    return db.query(Photo).filter(Photo.hash == hash_str).first()

def create_photo_record(db: Session, hash_str: str, file_path: str, file_created_at: datetime = None) -> Photo:
    photo = Photo(hash=hash_str, file_path=file_path, file_created_at=file_created_at)
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return photo

def get_or_create_photo(db: Session, filepath: str, file_created_at: datetime = None):
    file_hash = generate_file_hash(filepath)
    photo = check_photo_hash_exists(db, file_hash)
    if not photo:
        photo = create_photo_record(db, file_hash, filepath, file_created_at)
    return photo

def get_photo_by_id(db: Session, photo_id: int) -> Photo | None:
    return db.query(Photo).filter(Photo.id == photo_id).first()

def get_all_photos(db: Session) -> List[Photo]:
    return db.query(Photo).all()

def update_model_status(db: Session, name: str, status: str):
    state = db.query(ModelState).filter_by(name=name).first()
    if not state:
        state = ModelState(name=name, status=status)
        db.add(state)
    else:
        state.status = status
    db.commit()
    db.refresh(state)
    return state

def get_model_status(db: Session, name: str) -> Optional[str]:
    """Returns the current status string for a model, or None if not found."""
    state = db.query(ModelState).filter_by(name=name).first()
    return state.status if state else None

def get_all_model_states(db: Session):
    return db.query(ModelState).all()

# Semantic Relational Helpers
def get_or_create_camera(db: Session, make: str, model: str):
    camera = db.query(Camera).filter_by(make=make, model=model).first()
    if not camera:
        camera = Camera(make=make, model=model)
        db.add(camera)
        db.commit()
        db.refresh(camera)
    return camera

def get_or_create_keyword(db: Session, name: str):
    kw = db.query(Keyword).filter_by(name=name).first()
    if not kw:
        kw = Keyword(name=name)
        db.add(kw)
        db.commit()
        db.refresh(kw)
    return kw

def update_photo_geoposition(db: Session, photo_id: int, lat: float, lon: float, address: str = None):
    geo = db.query(Geoposition).filter_by(photo_id=photo_id).first()
    if not geo:
        geo = Geoposition(photo_id=photo_id, latitude=lat, longitude=lon, address=address)
        db.add(geo)
    else:
        geo.latitude = lat
        geo.longitude = lon
        geo.address = address
    db.commit()
    return geo

# Quantitative Tagging & Categorization
def get_or_create_tag(db: Session, name: str):
    tag = db.query(Tag).filter_by(name=name).first()
    if not tag:
        tag = Tag(name=name)
        db.add(tag)
        db.commit()
        db.refresh(tag)
    return tag

def add_photo_tag_with_score(db: Session, photo_id: int, tag_name: str, score: float):
    logger.info(f"Adding tag: {tag_name} with score: {score}")
    tag = get_or_create_tag(db, tag_name)
    logger.info(f"Tag: {tag.id}")
    photo = get_photo_by_id(db, photo_id)
    logger.info(f"Photo: {photo}")
    photo_tag = db.query(PhotoTag).filter_by(photo_id=photo_id, tag_id=tag.id).first()
    logger.info(f"Photo tag: {photo_tag}")
    if not photo_tag:
        photo_tag = PhotoTag(photo=photo, tag=tag, confidence_score=score)
        db.add(photo_tag)
        logger.info(f"Added photo tag")
    else:
        photo_tag.confidence_score = score
    db.commit()
    logger.info(f"Committed photo tag")
    photo_tag = db.query(PhotoTag).filter_by(photo_id=photo_id, tag_id=tag.id).first()
    return photo_tag

def get_or_create_category(db: Session, name: str, prompt: str = ""):
    cat = db.query(Category).filter_by(name=name).first()
    if not cat:
        cat = Category(name=name, prompt=prompt)
        db.add(cat)
        db.commit()
        db.refresh(cat)
    return cat

def get_category_by_id(db: Session, cat_id: int):
    return db.query(Category).filter_by(id=cat_id).first()

def get_all_categories(db: Session) -> List[Category]:
    return db.query(Category).all()

def add_photo_category_with_score(db: Session, photo_id: int, cat_id: int, score: float):
    photo_cat = db.query(PhotoCategory).filter_by(photo_id=photo_id, category_id=cat_id).first()
    if not photo_cat:
        photo_cat = PhotoCategory(photo_id=photo_id, category_id=cat_id, confidence_score=score)
        db.add(photo_cat)
    else:
        photo_cat.confidence_score = score
    db.commit()
    return photo_cat

def get_or_create_watcher(db: Session, path: str):
    watcher = db.query(Watcher).filter_by(path=path).first()
    if not watcher:
        watcher = Watcher(path=path)
        db.add(watcher)
        db.commit()
        db.refresh(watcher)
    return watcher

def get_watcher_by_id(db: Session, watcher_id: int):
    return db.query(Watcher).filter_by(id=watcher_id).first() 

def update_watcher_status(db: Session, watcher_id: int, status: str):
    watcher = db.query(Watcher).filter_by(id=watcher_id).first()
    watcher.status = status
    db.commit()
    return watcher

def get_all_active_watchers(db: Session):
    return db.query(Watcher).filter(Watcher.status == "active").all()

def get_all_watchers(db: Session):
    return db.query(Watcher).all()