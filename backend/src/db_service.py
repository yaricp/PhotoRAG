from sqlalchemy.orm import Session
from src.models import (
    Photo, ModelState, Camera, Geoposition, 
    Keyword, Tag, Person, Category, PhotoTag, PhotoCategory
)
from src.watcher import generate_file_hash
from datetime import datetime

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
    tag = get_or_create_tag(db, tag_name)
    photo_tag = db.query(PhotoTag).filter_by(photo_id=photo_id, tag_id=tag.id).first()
    if not photo_tag:
        photo_tag = PhotoTag(photo_id=photo_id, tag_id=tag.id, confidence_score=score)
        db.add(photo_tag)
    else:
        photo_tag.confidence_score = score
    db.commit()
    return photo_tag

def get_or_create_category(db: Session, name: str):
    cat = db.query(Category).filter_by(name=name).first()
    if not cat:
        cat = Category(name=name)
        db.add(cat)
        db.commit()
        db.refresh(cat)
    return cat

def get_all_categories(db: Session):
    return [c.name for c in db.query(Category).all()]

def add_photo_category_with_score(db: Session, photo_id: int, cat_name: str, score: float):
    cat = get_or_create_category(db, cat_name)
    photo_cat = db.query(PhotoCategory).filter_by(photo_id=photo_id, category_id=cat.id).first()
    if not photo_cat:
        photo_cat = PhotoCategory(photo_id=photo_id, category_id=cat.id, confidence_score=score)
        db.add(photo_cat)
    else:
        photo_cat.confidence_score = score
    db.commit()
    return photo_cat
