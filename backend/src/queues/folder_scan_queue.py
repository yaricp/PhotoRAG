import asyncio
import os
from datetime import datetime

from huey import SqliteHuey
from loguru import logger

from src.db.database import SessionLocal
from src.db_service import (
    check_photo_hash_exists,
    create_photo_record,
    delete_folder_scanner,
    get_or_create_folder_scanner,
    record_exact_duplicate,
    update_folder_scanner_progress,
)
from src.models import FolderScanner
from src.utils import check_if_file_is_image, generate_file_hash

folder_scan_queue = SqliteHuey(
    "folder_scan",
    filename=os.path.join(os.environ.get("QUEUE_DB_DIR", os.path.join(os.getcwd(), "..")), "folder_scan.sqlite3"),
)


@folder_scan_queue.task()
def start_folder_scanner_task(path: str) -> bool:
    """
    Scan a folder and process all photos in parallel.

    Pass 1 (sync): walk directory, hash files, register new photos in DB.
    Pass 2 (async): run all photo pipelines concurrently via run_pipelines_batch.
    """
    if not os.path.exists(path):
        logger.error(f"[folder_scan] Path does not exist: {path}")
        return False

    # ── Pass 1: collect image files ────────────────────────────────────────
    image_paths = []
    for root, _, files in os.walk(path):
        for file in files:
            fp = os.path.join(root, file)
            if check_if_file_is_image(fp):
                image_paths.append(fp)

    total_steps = len(image_paths) * 3
    logger.info(f"[folder_scan] '{path}': {len(image_paths)} images, {total_steps} steps")

    db = SessionLocal()
    try:
        folder_scanner = get_or_create_folder_scanner(db, path, total_steps)
        db.commit()
        db.refresh(folder_scanner)
        scanner_id = folder_scanner.id
        logger.info(f"[folder_scan] scanner_id={scanner_id}")
    finally:
        db.close()

    # ── Pass 1: register photos, skip exact duplicates ─────────────────────
    new_photo_ids: list[int] = []

    for file_path in image_paths:
        logger.info(f"[folder_scan] Processing: {file_path}")
        try:
            file_hash = generate_file_hash(file_path)
            stat = os.stat(file_path)
            file_created_at = datetime.fromtimestamp(getattr(stat, "st_birthtime", stat.st_ctime))

            db = SessionLocal()
            try:
                existing = check_photo_hash_exists(db, file_hash)
                if existing:
                    logger.info(f"[folder_scan] Exact duplicate: {file_path}")
                    record_exact_duplicate(db, existing.id, file_path)
                    update_folder_scanner_progress(db, scanner_id)
                    db.commit()
                    continue

                photo = create_photo_record(db, file_hash, file_path, file_created_at)
                db.commit()
                new_photo_ids.append(photo.id)
                logger.info(f"[folder_scan] Registered photo_id={photo.id}: {file_path}")
            except Exception as exc:
                logger.error(f"[folder_scan] DB error for {file_path}: {exc}")
                db.rollback()
            finally:
                db.close()

        except Exception as exc:
            logger.error(f"[folder_scan] Error processing {file_path}: {exc}")

    if not new_photo_ids:
        logger.info("[folder_scan] No new photos to process.")
        return True

    # ── Pass 2: run all pipelines concurrently ─────────────────────────────
    logger.info(f"[folder_scan] Launching pipelines for {len(new_photo_ids)} photos")
    from src.incoming_pipeline import run_pipelines_batch

    asyncio.run(run_pipelines_batch(new_photo_ids, scanner_id))
    logger.info("[folder_scan] All pipelines complete.")
    return True


def start_existing_folder_scanners() -> None:
    db = SessionLocal()
    try:
        folder_scanners = db.query(FolderScanner).all()
        for fs in folder_scanners:
            if fs.scanned_steps < fs.total_steps:
                logger.info(f"[folder_scan] Resuming scanner {fs.id}")
                start_folder_scanner_task(fs.path)
            else:
                logger.info(f"[folder_scan] Scanner {fs.id} done, removing")
                delete_folder_scanner(db, fs.id)
        db.commit()
    finally:
        db.close()
