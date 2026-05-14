"""Phase-0 CPU tasks and phase-1 CLIP tasks — called by incoming_pipeline.py."""
import asyncio
from time import time
from loguru import logger

from src.db.database import SessionLocal
from src.db_service import (
    get_photo_by_id,
    get_or_create_camera,
    update_photo_geoposition,
    add_photo_tag_with_score,
    get_or_create_category,
    add_photo_category_with_score,
    get_or_create_photo_hash,
    find_perceptual_duplicates,
    record_perceptual_duplicate,
    create_quality_issue,
)
from src.model_services import call_clip_model
from src.pipeline_tracker import track_task
from src.utils import extract_exif, parse_datetime
from src.quality_checks import check_resolution, check_exif


# ---------------------------------------------------------------------------
# Phase 0 — CPU-only, run via asyncio.to_thread so they don't block the loop
# ---------------------------------------------------------------------------

def _metadata_sync(photo_id: int) -> None:
    from src.geo import GeoEnricher
    db = SessionLocal()
    try:
        photo = get_photo_by_id(db, photo_id)
        if not photo:
            return

        exif_raw = extract_exif(photo.file_path)
        photo.captured_at = parse_datetime(exif_raw)

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

        is_thumbnail, px_count = check_resolution(photo.file_path)
        if is_thumbnail:
            create_quality_issue(db, photo.id, "thumbnail", px_count)

        is_no_exif, _ = check_exif(exif_raw)
        if is_no_exif:
            create_quality_issue(db, photo.id, "no_exif", 0.0)

        db.commit()
        logger.info(f"[metadata] Photo {photo_id} done ✓")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def metadata_task(photo_id: int) -> None:
    """Extract EXIF, geolocation, and camera info — CPU-only, runs in thread pool."""
    logger.info(f"[metadata] Start: photo_id={photo_id}")
    async with track_task(photo_id, "phase_0", "metadata_task"):
        await asyncio.to_thread(_metadata_sync, photo_id)


def _perceptual_hashes_sync(photo_id: int) -> None:
    import imagehash
    from PIL import Image

    db = SessionLocal()
    try:
        photo = get_photo_by_id(db, photo_id)
        if not photo:
            return

        try:
            img = Image.open(photo.file_path)
            dhash_val = str(imagehash.dhash(img))
            ahash_val = str(imagehash.average_hash(img))
            phash_val = str(imagehash.phash(img))

            get_or_create_photo_hash(db, photo_id, dhash=dhash_val, ahash=ahash_val, phash=phash_val)

            near_dupes = find_perceptual_duplicates(db, photo_id, threshold=10)
            for match in near_dupes:
                record_perceptual_duplicate(db, photo_id, match["photo_id"], match["hash_distance"])
            db.commit()
            logger.info(f"[perceptual] Photo {photo_id}: hashes saved ✓")
        except Exception as hash_err:
            logger.warning(f"[perceptual] Hash failed for photo {photo_id}: {hash_err} — skipping")
            db.rollback()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def compute_perceptual_hashes_task(photo_id: int) -> None:
    """Compute dHash/aHash/pHash and detect near-duplicate photos — runs in thread pool."""
    logger.info(f"[perceptual] Start: photo_id={photo_id}")
    async with track_task(photo_id, "phase_0", "compute_perceptual_hashes_task"):
        await asyncio.to_thread(_perceptual_hashes_sync, photo_id)


# ---------------------------------------------------------------------------
# Phase 1 — CLIP model calls (async, poll Huey worker)
# DB reads and writes run in threads so the event loop stays free.
# ---------------------------------------------------------------------------

def _get_file_path_sync(photo_id: int) -> str | None:
    db = SessionLocal()
    try:
        photo = get_photo_by_id(db, photo_id)
        return photo.file_path if photo else None
    finally:
        db.close()


def _save_tags_sync(photo_id: int, tags: list) -> None:
    db = SessionLocal()
    try:
        for tag_name, score in tags:
            add_photo_tag_with_score(db, photo_id, tag_name, score)
            logger.debug(f"[clip/tags] Photo {photo_id}: tag '{tag_name}' score={score:.3f}")
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _save_categories_sync(photo_id: int, cat_results: list) -> None:
    db = SessionLocal()
    try:
        for cat_name, score in cat_results:
            cat = get_or_create_category(db, cat_name)
            add_photo_category_with_score(db, photo_id, cat.id, score)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def auto_tag_clip_task(photo_id: int) -> None:
    """CLIP: find tags for photo."""
    logger.info(f"[clip/tags] Start: photo_id={photo_id}")
    async with track_task(photo_id, "phase_1", "auto_tag_clip_task"):
        file_path = await asyncio.to_thread(_get_file_path_sync, photo_id)
        if not file_path:
            return
        t0 = time()
        tags = await call_clip_model(file_path, task="tags")
        logger.debug(f"[clip/tags] Photo {photo_id}: model took {time()-t0:.2f}s, {len(tags)} tags")
        await asyncio.to_thread(_save_tags_sync, photo_id, tags)
        logger.info(f"[clip/tags] Photo {photo_id}: {len(tags)} tags ✓")


async def categorize_photo_task(photo_id: int) -> None:
    """CLIP: determine categories of photo."""
    logger.info(f"[clip/categories] Start: photo_id={photo_id}")
    async with track_task(photo_id, "phase_1", "categorize_photo_task"):
        file_path = await asyncio.to_thread(_get_file_path_sync, photo_id)
        if not file_path:
            return
        t0 = time()
        cat_results = await call_clip_model(file_path=file_path, task="categorize")
        logger.debug(f"[clip/categories] Photo {photo_id}: model took {time()-t0:.2f}s, {len(cat_results)} cats")
        await asyncio.to_thread(_save_categories_sync, photo_id, cat_results)
        logger.info(f"[clip/categories] Photo {photo_id}: {len(cat_results)} categories ✓")
