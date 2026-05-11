from typing import Optional, List
from datetime import datetime
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy import exists, and_, text, extract, func

from src.models import (
    Photo, Tag, Person, Keyword, Category, PhotoTag, PhotoCategory, Camera, Geoposition,
    ModelState, Watcher, ProcessingJob, FolderScanner, AIModelConfig,
    PhotoEmbedding, PhotoHash, PhotoDuplicate, PhotoQualityIssue,
    AppSetting, HistoryAction,
)
from src.schemas import Photo as PhotoSchema
from src.schemas import AIModelConfigUpdate
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


def get_photo_by_id(db: Session, photo_id: int) -> Optional[Photo]:
    return db.query(Photo).filter(Photo.id == photo_id).first()


def get_photos_by_category_id(db: Session, category_id: int) -> List[Photo]:
    return db.query(Photo).filter(
        Photo.is_archived == False,
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
    is_doc: Optional[bool] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    day: Optional[int] = None,
):

    base_query = db.query(Photo).filter(Photo.is_archived == False)

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

    if geoposition_id is not None:
        base_query = base_query.filter(Photo.geoposition_id == geoposition_id)

    # 🔹 документ
    if is_doc is not None:
        base_query = base_query.filter(Photo.is_doc == is_doc)

    if year is not None:
        base_query = base_query.filter(extract('year', Photo.captured_at) == year)
    if month is not None:
        base_query = base_query.filter(extract('month', Photo.captured_at) == month)
    if day is not None:
        base_query = base_query.filter(extract('day', Photo.captured_at) == day)

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


def get_available_dates(
    db: Session,
    category_ids: Optional[list[int]] = None,
    tag_ids: Optional[list[int]] = None,
    camera_id: Optional[int] = None,
    geoposition_id: Optional[int] = None,
) -> list[dict]:
    from sqlalchemy import func
    base_query = db.query(
        extract('year', Photo.captured_at).label('year'),
        extract('month', Photo.captured_at).label('month'),
        extract('day', Photo.captured_at).label('day'),
    ).filter(Photo.captured_at.isnot(None), Photo.is_archived == False)

    if category_ids:
        for cid in category_ids:
            base_query = base_query.filter(
                exists().where(and_(PhotoCategory.photo_id == Photo.id, PhotoCategory.category_id == cid))
            )
    if tag_ids:
        for tid in tag_ids:
            base_query = base_query.filter(
                exists().where(and_(PhotoTag.photo_id == Photo.id, PhotoTag.tag_id == tid))
            )
    if camera_id is not None:
        base_query = base_query.filter(Photo.camera_id == camera_id)
    if geoposition_id is not None:
        base_query = base_query.filter(Photo.geoposition_id == geoposition_id)

    rows = base_query.distinct().all()
    return [{'year': int(r.year), 'month': int(r.month), 'day': int(r.day)} for r in rows]


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
        if photo and not photo.is_archived:
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
    lat = round(lat, 3)
    lon = round(lon, 3)

    geo = db.query(Geoposition).filter_by(latitude=lat, longitude=lon, address=address).first()
    if not geo:
        geo = Geoposition(latitude=lat, longitude=lon, address=address)
        db.add(geo)
        db.flush()

    photo = db.query(Photo).filter_by(id=photo_id).first()
    if photo:
        photo.geoposition_id = geo.id

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
    db.query(ProcessingJob).filter_by(photo_id=photo_id).delete()
    photo.geoposition_id = None
    try:
        db.execute(text("DELETE FROM photo_embeddings_vss WHERE rowid = :id"), {"id": photo_id})
    except Exception:
        pass  # virtual table may not exist in all environments (e.g. tests)
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


def get_or_create_folder_scanner(db: Session, path: str, total_steps: int):
    folder_scanner = db.query(FolderScanner).filter_by(path=path).first()
    if not folder_scanner:
        folder_scanner = FolderScanner(
            path=path, total_steps=total_steps, scanned_steps=0
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
        scanner.scanned_steps += 1
        db.commit()
        logger.info(f"scanned steps: {scanner.scanned_steps}")
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


def get_all_model_configs(db: Session):
    return db.query(AIModelConfig).all()


def get_model_config(db: Session, config_type: str):
    return db.query(AIModelConfig).filter_by(type=config_type).first()


def update_model_config(db: Session, config_type: str, schema: AIModelConfigUpdate):
    config = db.query(AIModelConfig).filter_by(type=config_type).first()
    if config:
        config.mode = schema.mode
        config.model_name = schema.model_name
        config.url = schema.url
        config.api_key = schema.api_key
        db.commit()
        db.refresh(config)
    return config


def init_default_model_configs(db: Session):
    defaults = [
        {"type": "vision", "mode": "local", "model_name": "Qwen/Qwen2-VL-2B-Instruct"},
        {"type": "clip", "mode": "local", "model_name": "ViT-B-32"},
        {"type": "embedding", "mode": "local", "model_name": "nomic-ai/nomic-embed-text-v1.5"},
        {"type": "translator", "mode": "local", "model_name": "facebook/nllb-200-distilled-600M"},
        {"type": "chat", "mode": "remote", "model_name": "gpt-4o-mini"},
        {"type": "ocr", "mode": "local", "model_name": "easyocr"},
    ]
    
    for d in defaults:
        config = db.query(AIModelConfig).filter_by(type=d["type"]).first()
        if not config:
            config = AIModelConfig(**d)
            db.add(config)

    db.commit()


# ── Duplicate helpers ──────────────────────────────────────────────────────────

def record_exact_duplicate(db: Session, original_id: int, duplicate_file_path: str) -> Optional[PhotoDuplicate]:
    original = db.query(Photo).filter(Photo.id == original_id).first()
    if original and original.file_path == duplicate_file_path:
        return None  # same file scanned twice — not a duplicate
    existing = db.query(PhotoDuplicate).filter_by(
        original_photo_id=original_id,
        duplicate_file_path=duplicate_file_path,
        match_type="exact",
    ).first()
    if existing:
        return existing
    record = PhotoDuplicate(
        original_photo_id=original_id,
        duplicate_file_path=duplicate_file_path,
        match_type="exact",
        hash_distance=None,
    )
    db.add(record)
    db.commit()
    return record


def record_perceptual_duplicate(db: Session, original_id: int, duplicate_id: int, distance: int) -> PhotoDuplicate:
    existing = db.query(PhotoDuplicate).filter_by(
        original_photo_id=original_id,
        duplicate_photo_id=duplicate_id,
        match_type="perceptual",
    ).first()
    if existing:
        return existing
    record = PhotoDuplicate(
        original_photo_id=original_id,
        duplicate_photo_id=duplicate_id,
        match_type="perceptual",
        hash_distance=distance,
    )
    db.add(record)
    db.commit()
    return record


def get_or_create_photo_hash(
    db: Session, photo_id: int, dhash: str, ahash: str, phash: str
) -> PhotoHash:
    ph = db.query(PhotoHash).filter_by(photo_id=photo_id).first()
    if ph:
        return ph
    ph = PhotoHash(photo_id=photo_id, dhash=dhash, ahash=ahash, phash=phash)
    db.add(ph)
    db.commit()
    db.refresh(ph)
    return ph


def _hamming_distance(hex_a: str, hex_b: str) -> int:
    """Hamming distance between two hex-encoded hash strings."""
    try:
        a = int(hex_a, 16)
        b = int(hex_b, 16)
    except (ValueError, TypeError):
        return 999
    return bin(a ^ b).count("1")


def find_perceptual_duplicates(
    db: Session, photo_id: int, threshold: int = 10
) -> list[dict]:
    """
    Return list of {photo_id, hash_distance} for all photos whose dhash is
    within `threshold` hamming distance of the given photo's dhash.
    Excludes the photo itself.
    """
    source = db.query(PhotoHash).filter_by(photo_id=photo_id).first()
    if not source or not source.dhash:
        return []

    candidates = db.query(PhotoHash).filter(PhotoHash.photo_id != photo_id).all()
    results = []
    for candidate in candidates:
        dist = _hamming_distance(source.dhash, candidate.dhash)
        if dist <= threshold:
            results.append({"photo_id": candidate.photo_id, "hash_distance": dist})
    return results


def get_duplicate_groups(db: Session) -> dict:
    """
    Return all duplicate relationships grouped by match_type.
    Shape: {"exact": [...], "perceptual": [...]}
    exact item:      {"original": {id, file_path}, "duplicates": [{file_path}]}
    perceptual item: {"original": {id, file_path}, "duplicates": [{id, file_path, hash_distance}]}
    """
    rows = db.query(PhotoDuplicate).all()

    exact: dict[int, dict] = {}
    perceptual: dict[int, dict] = {}

    for row in rows:
        orig = row.original_photo
        if orig.is_archived:
            continue
        orig_data = {"id": orig.id, "file_path": orig.file_path}

        if row.match_type == "exact":
            dup_data = {"id": row.id, "file_path": row.duplicate_file_path}
            if orig.id not in exact:
                exact[orig.id] = {"original": orig_data, "duplicates": []}
            exact[orig.id]["duplicates"].append(dup_data)
        else:
            dup = row.duplicate_photo
            if dup.is_archived:
                continue
            dup_data = {
                "id": dup.id,
                "file_path": dup.file_path,
                "hash_distance": row.hash_distance,
            }
            if orig.id not in perceptual:
                perceptual[orig.id] = {"original": orig_data, "duplicates": []}
            perceptual[orig.id]["duplicates"].append(dup_data)

    return {
        "exact": list(exact.values()),
        "perceptual": list(perceptual.values()),
    }


def archive_photo(db: Session, photo_id: int) -> Optional[Photo]:
    photo = db.query(Photo).filter(Photo.id == photo_id).first()
    if not photo:
        return None
    photo.is_archived = True
    db.commit()
    db.refresh(photo)
    return photo


def delete_duplicate_record(db: Session, record_id: int) -> Optional[PhotoDuplicate]:
    record = db.query(PhotoDuplicate).filter(PhotoDuplicate.id == record_id).first()
    if not record:
        return None
    db.delete(record)
    db.commit()
    return record


# ── Quality issue helpers ──────────────────────────────────────────────────

def create_quality_issue(
    db: Session, photo_id: int, issue_type: str, score: Optional[float]
) -> PhotoQualityIssue:
    issue = PhotoQualityIssue(photo_id=photo_id, issue_type=issue_type, score=score)
    db.add(issue)
    return issue


def get_quality_summary(db: Session) -> dict[str, int]:
    """Return count of distinct non-archived photos flagged per issue_type."""
    rows = (
        db.query(PhotoQualityIssue.issue_type, func.count(PhotoQualityIssue.photo_id.distinct()))
        .join(Photo, Photo.id == PhotoQualityIssue.photo_id)
        .filter(Photo.is_archived == False)
        .group_by(PhotoQualityIssue.issue_type)
        .all()
    )
    return {issue_type: count for issue_type, count in rows}


def get_photos_by_issue_type(
    db: Session, issue_type: str, skip: int = 0, limit: int = 20
) -> tuple[list[Photo], int]:
    """Return paginated photos that have been flagged with the given issue_type."""
    query = (
        db.query(Photo)
        .join(PhotoQualityIssue, Photo.id == PhotoQualityIssue.photo_id)
        .filter(PhotoQualityIssue.issue_type == issue_type, Photo.is_archived == False)
        .distinct()
    )
    total = query.count()
    photos = query.offset(skip).limit(limit).all()
    return photos, total


# ---------------------------------------------------------------------------
# Garbage / quality-issue helpers
# ---------------------------------------------------------------------------

def get_garbage_photos_with_issues(
    db: Session, issue_type: str = "", skip: int = 0, limit: int = 20
) -> tuple[list[Photo], int]:
    """Return paginated photos that have any quality issue, or a specific one."""
    query = (
        db.query(Photo)
        .join(PhotoQualityIssue, Photo.id == PhotoQualityIssue.photo_id)
        .filter(Photo.is_archived == False)
        .distinct()
    )
    if issue_type:
        query = query.filter(PhotoQualityIssue.issue_type == issue_type)
    total = query.count()
    photos = query.offset(skip).limit(limit).all()
    return photos, total


def get_garbage_photo_paths(db: Session, issue_type: str = "") -> list[str]:
    """Return file_path for all photos flagged with any (or a specific) quality issue."""
    query = (
        db.query(Photo.file_path)
        .join(PhotoQualityIssue, Photo.id == PhotoQualityIssue.photo_id)
        .filter(Photo.is_archived == False)
        .distinct()
    )
    if issue_type:
        query = query.filter(PhotoQualityIssue.issue_type == issue_type)
    return [row[0] for row in query.all()]


# ---------------------------------------------------------------------------
# Tag / category lookup by ID
# ---------------------------------------------------------------------------

def get_photos_by_tag_id(db: Session, tag_id: int) -> List[Photo]:
    """Return all photos that have a given tag."""
    return (
        db.query(Photo)
        .join(PhotoTag, Photo.id == PhotoTag.photo_id)
        .filter(PhotoTag.tag_id == tag_id, Photo.is_archived == False)
        .all()
    )


# ---------------------------------------------------------------------------
# EXIF-parameter search
# ---------------------------------------------------------------------------

def search_photos_by_exif_params(
    db: Session,
    width_min: Optional[int] = None,
    width_max: Optional[int] = None,
    height_min: Optional[int] = None,
    height_max: Optional[int] = None,
    focal_length_min: Optional[float] = None,
    focal_length_max: Optional[float] = None,
    aperture_min: Optional[float] = None,
    aperture_max: Optional[float] = None,
    iso_min: Optional[int] = None,
    iso_max: Optional[int] = None,
    camera_make: Optional[str] = None,
    camera_model: Optional[str] = None,
    limit: int = 50,
) -> List[Photo]:
    query = db.query(Photo).filter(Photo.is_archived == False)
    if camera_make or camera_model:
        query = query.join(Camera, Photo.camera_id == Camera.id, isouter=True)
    if width_min is not None:
        query = query.filter(Photo.image_width >= width_min)
    if width_max is not None:
        query = query.filter(Photo.image_width <= width_max)
    if height_min is not None:
        query = query.filter(Photo.image_height >= height_min)
    if height_max is not None:
        query = query.filter(Photo.image_height <= height_max)
    if focal_length_min is not None:
        query = query.filter(Photo.focal_length >= focal_length_min)
    if focal_length_max is not None:
        query = query.filter(Photo.focal_length <= focal_length_max)
    if aperture_min is not None:
        query = query.filter(Photo.aperture >= aperture_min)
    if aperture_max is not None:
        query = query.filter(Photo.aperture <= aperture_max)
    if iso_min is not None:
        query = query.filter(Photo.iso >= iso_min)
    if iso_max is not None:
        query = query.filter(Photo.iso <= iso_max)
    if camera_make:
        query = query.filter(Camera.make.ilike(f"%{camera_make}%"))
    if camera_model:
        query = query.filter(Camera.model.ilike(f"%{camera_model}%"))
    return query.limit(limit).all()


# ---------------------------------------------------------------------------
# AppSetting helpers
# ---------------------------------------------------------------------------

def get_setting(db: Session, key: str) -> Optional[str]:
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    return row.value if row else None


def set_setting(db: Session, key: str, value: str) -> AppSetting:
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if row:
        row.value = value
    else:
        row = AppSetting(key=key, value=value)
        db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_all_settings(db: Session) -> dict:
    rows = db.query(AppSetting).all()
    return {r.key: r.value for r in rows}


# ---------------------------------------------------------------------------
# HistoryAction helpers
# ---------------------------------------------------------------------------

def create_history_action(
    db: Session,
    action_type: str,
    photo_ids: Optional[List[int]],
    params: dict,
    undo_data: dict,
) -> HistoryAction:
    import json
    action = HistoryAction(
        action_type=action_type,
        photo_ids=json.dumps(photo_ids) if photo_ids is not None else None,
        params=json.dumps(params),
        undo_data=json.dumps(undo_data),
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    return action


def get_history_actions(db: Session, limit: int = 20) -> List[HistoryAction]:
    return (
        db.query(HistoryAction)
        .order_by(HistoryAction.created_at.desc())
        .limit(limit)
        .all()
    )


def get_last_history_action(db: Session) -> Optional[HistoryAction]:
    return (
        db.query(HistoryAction)
        .order_by(HistoryAction.created_at.desc())
        .first()
    )


def delete_history_action(db: Session, action_id: int) -> None:
    action = db.query(HistoryAction).filter(HistoryAction.id == action_id).first()
    if action:
        db.delete(action)
        db.commit()


def perform_undo(db: Session) -> str:
    import json
    import os
    import shutil
    import zipfile
    from pathlib import Path

    action = get_last_history_action(db)
    if not action:
        return "No action to undo."

    undo_data = json.loads(action.undo_data)

    if action.action_type == "create_folder":
        path = Path(undo_data["path"])
        if path.exists():
            try:
                path.rmdir()
            except OSError:
                return f"Cannot undo: folder '{path}' is not empty."

    elif action.action_type == "move_photos":
        original_paths = undo_data.get("original_paths", {})
        for photo_id_str, original_path in original_paths.items():
            photo = get_photo_by_id(db, int(photo_id_str))
            if photo and os.path.exists(photo.file_path):
                dest_dir = os.path.dirname(original_path)
                os.makedirs(dest_dir, exist_ok=True)
                shutil.move(photo.file_path, original_path)
                photo.file_path = original_path
        db.commit()

    elif action.action_type == "archive_photos":
        zip_path = Path(undo_data["zip_path"])
        # original_paths: dict[arcname → original_file_path] (new format)
        # added_names: list[arcname] (legacy format — no file restoration possible)
        original_paths: dict = undo_data.get("original_paths", {})
        added_names = set(original_paths.keys()) if original_paths else set(undo_data.get("added_names", []))
        newly_archived_ids = undo_data.get("newly_archived_ids", [])
        if zip_path.exists() and added_names:
            # Restore files to their original locations
            if original_paths:
                with zipfile.ZipFile(zip_path) as zf:
                    names_in_zip = set(zf.namelist())
                    for arcname, orig_path in original_paths.items():
                        if arcname in names_in_zip:
                            os.makedirs(os.path.dirname(orig_path), exist_ok=True)
                            with open(orig_path, "wb") as fout:
                                fout.write(zf.read(arcname))
                            logger.info(f"Restored {arcname} → {orig_path}")
            # Remove restored entries from zip
            with zipfile.ZipFile(zip_path) as zf:
                all_names = set(zf.namelist())
            remaining = all_names - added_names
            if not remaining:
                zip_path.unlink()
            else:
                tmp = zip_path.with_suffix(".tmp.zip")
                with zipfile.ZipFile(zip_path) as src, zipfile.ZipFile(tmp, "w") as dst:
                    for name in src.namelist():
                        if name not in added_names:
                            dst.writestr(name, src.read(name))
                tmp.replace(zip_path)
        for pid in newly_archived_ids:
            photo = get_photo_by_id(db, pid)
            if photo:
                photo.is_archived = False
        db.commit()

    elif action.action_type == "add_tag":
        tag_id = undo_data.get("tag_id")
        tagged_ids = undo_data.get("photo_ids", [])
        if tag_id and tagged_ids:
            db.query(PhotoTag).filter(
                PhotoTag.tag_id == tag_id,
                PhotoTag.photo_id.in_(tagged_ids),
            ).delete(synchronize_session=False)
            db.commit()

    elif action.action_type == "add_category":
        category_id = undo_data.get("category_id")
        cat_ids = undo_data.get("photo_ids", [])
        if category_id and cat_ids:
            db.query(PhotoCategory).filter(
                PhotoCategory.category_id == category_id,
                PhotoCategory.photo_id.in_(cat_ids),
            ).delete(synchronize_session=False)
            db.commit()

    elif action.action_type == "add_geoposition":
        original_geo_ids = undo_data.get("original_geoposition_ids", {})
        for photo_id_str, original_geo_id in original_geo_ids.items():
            photo = get_photo_by_id(db, int(photo_id_str))
            if photo:
                photo.geoposition_id = original_geo_id
        db.commit()

    delete_history_action(db, action.id)
    return f"Undone: {action.action_type}"
