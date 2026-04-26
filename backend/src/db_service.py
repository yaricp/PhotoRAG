from sqlalchemy.orm import Session
from src.models import Photo, ModelState, Camera, Geoposition, Keyword, Tag, Person, Category
from src.watcher import generate_file_hash
from datetime import datetime

def check_photo_hash_exists(db: Session, hash_str: str) -> Photo:
    return db.query(Photo).filter(Photo.hash == hash_str).first()

def create_photo_record(db: Session, hash_str: str, file_path: str, file_created_at: datetime = None) -> Photo:
    photo = Photo(
        hash=hash_str, 
        file_path=file_path,
        file_created_at=file_created_at
    )
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

# Model State Helpers
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

# Semantic Upsert Helpers
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
