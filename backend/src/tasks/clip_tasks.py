from loguru import logger


from src.ai.registry import registry
from src.database import SessionLocal
from src.db_service import (
    get_photo_by_id,
    get_or_create_camera,
    update_photo_geoposition,
    add_photo_tag_with_score,
    get_or_create_category,
    add_photo_category_with_score,
    delete_job
)
from src.utils import extract_exif, parse_datetime
from src.queues.clip_queue import clip_queue

# ---------------------------------------------------------------------------
# CLIP tasks → clip_queue (воркер: src.queue.clip_queue)
# ---------------------------------------------------------------------------

@clip_queue.task()
def metadata_task(photo_id: int, phase: str, folder_scanner_id: int = None):
    """Extracts EXIF, geolocation, and camera info — does not require GPU."""
    logger.info(f"[metadata] Start metadata task: photo_id={photo_id}, phase={phase}")
    from src.geo import GeoEnricher
    from src.tasks.utils import _finish_task
    db = SessionLocal()
    try:
        photo = get_photo_by_id(db, photo_id)
        if not photo:
            db.rollback()
            _finish_task(
                photo_id=photo_id,
                phase=phase,
                name="metadata_task",
                folder_scanner_id=folder_scanner_id
            )
            return

        exif_raw = extract_exif(photo.file_path)
        logger.info(f"[metadata] Photo {photo_id} EXIF: {exif_raw}")
        photo.captured_at = parse_datetime(exif_raw)
        logger.info(f"[metadata] Photo {photo_id} captured_at: {photo.captured_at}")

        make = exif_raw.get("Make")
        model = exif_raw.get("Model")
        if make and model and model != "Unknown":
            camera = get_or_create_camera(db, make=make, model=model)
            photo.camera_id = camera.id

        geo_result = GeoEnricher().geocode_photo(exif_raw)
        if geo_result.get("latitude") and geo_result.get("longitude"):
            update_photo_geoposition(
                db, photo_id,
                geo_result["latitude"],
                geo_result["longitude"],
                geo_result["address"],
            )

        photo.image_width = exif_raw.get("ImageWidth")
        photo.image_height = exif_raw.get("ImageHeight")
        photo.iso = exif_raw.get("ISO") or exif_raw.get("ISOSpeedRatings")
        photo.aperture = exif_raw.get("ApertureValue")
        photo.focal_length = exif_raw.get("FocalLength")
        photo.shutter_speed = exif_raw.get("ExposureTime")
        photo.offset_time = exif_raw.get("OffsetTime") or exif_raw.get("OffsetTimeOriginal")
            
        db.commit()
        logger.info(f"[metadata] Photo {photo_id} metadata saved ✓")
        _finish_task(
            photo_id=photo_id,
            phase=phase,
            name="metadata_task",
            folder_scanner_id=folder_scanner_id
        )
    except Exception as e:
        logger.error(f"[metadata] Error for photo {photo_id}: {e}")
        db.rollback()  # ✅ ОБЯЗАТЕЛЬНО

        try:
            delete_job(db, photo_id, phase)
            db.commit()  # отдельная транзакция
        except Exception:
            db.rollback()
            logger.error(f"[metadata] Failed to delete job for photo {photo_id}")
            raise
    finally:
        db.close()


@clip_queue.task()
def auto_tag_clip_task(photo_id: int, phase: str, folder_scanner_id: int = None):
    """CLIP: search the tags for photo"""
    logger.info(f"[clip/tags] Start auto_tag_clip_task: photo_id={photo_id}, phase={phase}")
    from src.tasks.utils import _finish_task
    db = SessionLocal()
    try:
        photo = get_photo_by_id(db, photo_id)
        if not photo:
            db.rollback()
            _finish_task(
                photo_id=photo_id,
                phase=phase,
                name="auto_tag_clip_task",
                folder_scanner_id=folder_scanner_id
            )
            return

        confident_tags = registry.clip_tagger.find_tags(photo.file_path)
        # confident_tags = get_tags_from_remote_model(photo.file_path)
        logger.info(f"[clip/tags] Photo {photo_id}: {len(confident_tags)} tags found")
        for tag_name, score in confident_tags:
            add_photo_tag_with_score(db, photo_id, tag_name, score)

        db.commit()
        _finish_task(
            photo_id=photo_id,
            phase=phase,
            name="auto_tag_clip_task",
            folder_scanner_id=folder_scanner_id
        )
    except Exception as e:
        logger.error(f"[clip/tags] Error for photo {photo_id}: {e}")
        db.rollback()  # ✅ ОБЯЗАТЕЛЬНО

        try:
            delete_job(db, photo_id, phase)
            db.commit()  # отдельная транзакция
        except Exception:
            db.rollback()
            logger.error(f"[clip/tags] Failed to delete job for photo {photo_id}")
            raise
    finally:
        db.close()


@clip_queue.task()
def categorize_photo_task(photo_id: int, phase: str, folder_scanner_id: int = None):
    """CLIP: determine categories of photo"""
    logger.info(f"[clip/categories] Start categorize_photo_task: photo_id={photo_id}, phase={phase}")
    from src.tasks.utils import _finish_task
    db = SessionLocal()
    try:
        photo = get_photo_by_id(db, photo_id)
        if not photo:
            db.rollback()
            _finish_task(
                photo_id=photo_id,
                phase=phase,
                name="categorize_photo_task",
                folder_scanner_id=folder_scanner_id
            )
            return

        cat_results = registry.clip_tagger.categorize(photo.file_path)
        logger.info(f"[clip/categories] Photo {photo_id}: {len(cat_results)} categories")
        for cat_id, cat_name, score in cat_results:
            add_photo_category_with_score(db, photo_id, cat_id, score)

        db.commit()
        _finish_task(
            photo_id=photo_id,
            phase=phase,
            name="categorize_photo_task",
            folder_scanner_id=folder_scanner_id
        )
    except Exception as e:
        logger.error(f"[clip/categories] Error for photo {photo_id}: {e}")
        db.rollback()  # ✅ ОБЯЗАТЕЛЬНО

        try:
            delete_job(db, photo_id, phase)
            db.commit()  # отдельная транзакция
        except Exception:
            db.rollback()
            logger.error(f"[clip/categories] Failed to delete job for photo {photo_id}")
            raise
    finally:
        db.close()
