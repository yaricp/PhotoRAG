from sqlalchemy.orm import Session
from src.models import Photo, ModelState
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
