from typing import Optional, List
from datetime import datetime
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy import exists, and_, text

from src.models import (
    Photo, ModelState, Camera, Geoposition, 
    Keyword, Tag, Person, Category, PhotoTag, PhotoCategory,
    Watcher, ProcessingJob, PhotoEmbedding, FolderScanner
)
from src.schemas import Photo as PhotoSchema
from src.utils import generate_file_hash
from src.vector_db_services import search_similar_photos
from src.config  import Main_Settings


# Registration & Status Helpers (Existing)
def check_photo_hash_exists(db: Session, hash_str: str) -> Photo:
    return db.query(Photo).filter(Photo.hash == hash_str).first()


def create_photo_record(
    db: Session, hash_str: str, file_path: str,
    file_created_at: datetime = None
) -> Photo:
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


def get_photo_by_id(db: Session, photo_id: int) -> Photo | None:
    return db.query(Photo).filter(Photo.id == photo_id).first()


def get_photos_by_category_id(db: Session, category_id: int) -> List[Photo]:
    return db.query(Photo).filter(
        Photo.categories_rel.any(PhotoCategory.category_id == category_id)
    ).all()


def get_all_photos(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    category_ids: Optional[list[int]] = None,
    tag_ids: Optional[list[int]] = None,
    camera_id: Optional[int] = None,
    geoposition_id: Optional[int] = None,
    is_doc: Optional[bool] = None
):

    base_query = db.query(Photo)

    # 🔹 ВСЕ категории должны присутствовать (AND)
    if category_ids:
        for cid in category_ids:
            base_query = base_query.filter(
                exists().where(
                    and_(
                        PhotoCategory.photo_id == Photo.id,
                        PhotoCategory.category_id == cid
                    )
                )
            )

    # 🔹 ВСЕ теги должны присутствовать (AND)
    if tag_ids:
        for tid in tag_ids:
            base_query = base_query.filter(
                exists().where(
                    and_(
                        PhotoTag.photo_id == Photo.id,
                        PhotoTag.tag_id == tid
                    )
                )
            )

    # 🔹 камера
    if camera_id is not None:
        base_query = base_query.filter(Photo.camera_id == camera_id)

    # 🔹 geoposition
    if geoposition_id is not None:
        base_query = base_query.filter(Photo.geoposition_id == geoposition_id)

    # 🔹 документ
    if is_doc is not None:
        base_query = base_query.filter(Photo.is_doc == is_doc)

    # 🔥 важно: считаем ДО пагинации
    total = base_query.count()

    # 🔹 сортировка
    order_col = {
        "created_at": Photo.created_at,
        "captured_at": Photo.captured_at,
        "file_created_at": Photo.file_created_at,
        "id": Photo.id
    }.get(sort_by, Photo.created_at)

    order_expr = order_col.desc() if sort_order == "desc" else order_col.asc()

    photos = (
        base_query
        .order_by(order_expr)
        .offset(skip)
        .limit(limit)
        .all()
    )

    return photos, total


def get_photos_by_vector(
    db: Session, request_text: str, k: int
) -> List[Photo]:
    """Returns a list of photos that are similar to the query vector."""
    logger.info("Getting photos by vector")
    # pyrefly: ignore [missing-import]
    from src.ai.registry import registry
    settings = Main_Settings()

    if settings.DEFAULT_LANGUAGE != "en":
        logger.info("Translating request text to English")
        request_text = registry.translator.translate(request_text, backward=True)

    _ = registry.nomic_embedder
    embedding = registry.embedder_encode_text(
        text=request_text, purpose="search"
    )
    results = search_similar_photos(db=db, query_embedding=embedding, limit=k)
    logger.info(f"Photos found in DB: {results}")
    photo_ids = [item[0] for item in results]
    photos = []
    for photo_id in photo_ids:
        photo = get_photo_by_id(db, photo_id)
        photos.append(photo)
    logger.info(f"Photos found in DB: {photos}")
    return photos


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


def get_model_or_none(db: Session, name: str):
    return db.query(ModelState).filter_by(name=name).first()


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


def get_all_tags(db: Session) -> List[Tag]:
    return db.query(Tag).all()


def get_all_cameras(db: Session) -> List[Camera]:
    return db.query(Camera).all()


def get_all_geopositions(db: Session) -> List[Geoposition]:
    return db.query(Geoposition).all()


def add_photo_category_with_score(db: Session, photo_id: int, cat_id: int, score: float):
    photo_cat = db.query(PhotoCategory).filter_by(photo_id=photo_id, category_id=cat_id).first()
    if not photo_cat:
        photo_cat = PhotoCategory(photo_id=photo_id, category_id=cat_id, confidence_score=score)
        db.add(photo_cat)
    else:
        photo_cat.confidence_score = score
    db.commit()
    return photo_cat


def get_or_create_watcher(db: Session, path: str, destination_path: str):
    watcher = db.query(Watcher).filter_by(path=path).first()
    if not watcher:
        watcher = Watcher(path=path, destination_path=destination_path)
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


def delete_watcher(db: Session, watcher_id: int):
    watcher = db.query(Watcher).filter_by(id=watcher_id).first()
    db.delete(watcher)
    db.commit()
    return watcher


def get_all_active_watchers(db: Session):
    return db.query(Watcher).filter(Watcher.status == "active").all()


def get_all_watchers(db: Session):
    return db.query(Watcher).all()


def get_or_create_job(
    db: Session, photo_id: int, phase: str, tasks: str
):
    job = db.query(ProcessingJob).filter_by(photo_id=photo_id, phase=phase).first()
    if not job:
        job = ProcessingJob(
            photo_id=photo_id, phase=phase, tasks=tasks,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
    return job


def update_job_tasks(
    db: Session,
    photo_id: int,
    phase: str,
    tasks: str,
    new_phase: str = None
):
    logger.info(f"Updating job tasks for photo {photo_id}")
    logger.info(f"in phase {phase} with tasks {tasks}")
    logger.info(f"new phase {new_phase}")
    job = db.query(ProcessingJob).filter_by(photo_id=photo_id, phase=phase).first()
    logger.info(f"Job found: {job}")
    if job:
        job.tasks = tasks
        if new_phase is not None:
            job.phase = new_phase
        db.commit()
        logger.info(f"Job updated: {job}")
        return job
    else:
        return None


def get_all_jobs(db: Session):
    return db.query(ProcessingJob).all()


def delete_job(db: Session, photo_id: int, phase: str):
    job = db.query(ProcessingJob).filter_by(photo_id=photo_id, phase=phase).first()
    if job:
        db.delete(job)
        db.commit()
        logger.info(f"Job deleted for photo {photo_id} in phase {phase}")
        return True
    return False


def get_job_by_photo_id(db: Session, photo_id: int):
    return db.query(ProcessingJob).filter_by(photo_id=photo_id).first()


def delete_photo(db: Session, photo_id: int):
    photo = get_photo_by_id(db, photo_id)
    if not photo:
        return None
    
    db.query(PhotoEmbedding).filter_by(photo_id=photo_id).delete()
    db.query(PhotoTag).filter_by(photo_id=photo_id).delete()
    db.query(PhotoCategory).filter_by(photo_id=photo_id).delete()
    db.query(Geoposition).filter_by(photo_id=photo_id).delete()
    db.query(ProcessingJob).filter_by(photo_id=photo_id).delete()
    db.execute(text("DELETE FROM photo_embeddings_vss WHERE rowid = :id"), {"id": photo_id})
    db.delete(photo)
    
    db.flush()   # применяет изменения, но не закрывает сессию
    
    # photo ещё привязан к сессии, но уже "удалён" из БД
    # Pydantic может прочитать все атрибуты
    response = PhotoSchema.model_validate(photo)
    
    db.commit()  # теперь коммитим
    return response  # возвращаем уже готовую схему, не ORM-объект


def get_all_folder_scanners(db: Session):
    return db.query(FolderScanner).all()


def create_folder_scanner(db: Session, path: str):
    folder_scanner = FolderScanner(
        path=path, progress_percentage=0
    )
    db.add(folder_scanner)
    db.commit()
    db.refresh(folder_scanner)
    return folder_scanner


def get_folder_scanner(db: Session, id: int):
    return db.query(FolderScanner).filter_by(id=id).first()


def get_folder_scanner_by_path(db: Session, path: str):
    return db.query(FolderScanner).filter_by(path=path).first()


def get_or_create_folder_scanner(db: Session, path: str, total_files: int):
    folder_scanner = db.query(FolderScanner).filter_by(path=path).first()
    if not folder_scanner:
        folder_scanner = FolderScanner(
            path=path, total_files=total_files, scanned_files=0
        )
        db.add(folder_scanner)
        db.commit()
        db.refresh(folder_scanner)
    return folder_scanner


def update_folder_scanner_progress(db: Session, folder_scanner_id: int):
    """Update folder scanner progress"""
    logger.info(f"Updating folder scanner progress for folder scanner {folder_scanner_id}")
    scanner = db.query(FolderScanner).filter_by(id=folder_scanner_id).first()
    if scanner:
        scanner.scanned_files += 1
        db.commit()
        logger.info(f"scanned files: {scanner.scanned_files}")
        return scanner
    else:
        return "STOP"


def delete_folder_scanner(db: Session, id: int):
    folder_scanner = db.query(FolderScanner).filter_by(id=id).first()
    if folder_scanner:
        db.delete(folder_scanner)
        db.commit()
        logger.info(f"Folder scanner with ID {id} deleted")
        return folder_scanner
    logger.info(f"Folder scanner with ID {id} not found")
    return None
