import os
from loguru import logger
from datetime import datetime

from src.database import SessionLocal
from src.models import FolderScanner
from src.db_service import (
    update_folder_scanner_progress,
    check_photo_hash_exists,
    create_photo_record,
    delete_folder_scanner,
    get_or_create_folder_scanner
)
from src.tasks import start_pipeline
from src.utils import generate_file_hash, check_if_file_is_image
from src.queues.folder_scan_queue import folder_scan_queue


@folder_scan_queue.task()
def start_folder_scanner_task(path: str) -> bool:
    """Starts the folder scanner"""
    db = SessionLocal()
    if os.path.exists(path):
        list_of_photo_paths = []
        for root, _, files in os.walk(path):
            for file in files:
                file_path = os.path.join(root, file)
                if check_if_file_is_image(file_path):
                    list_of_photo_paths.append(file_path)
        total_steps = len(list_of_photo_paths) * 3
        logger.info(f"Folder '{path}' has {total_steps} steps")
        folder_scanner = get_or_create_folder_scanner(db, path, total_steps)
        db.commit()
        db.refresh(folder_scanner)
        logger.info(f"Folder scanner created: {folder_scanner.id}")
        logger.info(f"Folder scanner total_steps: {folder_scanner.total_steps}")
        logger.info(f"Folder scanner scanned_steps: {folder_scanner.scanned_steps}")
        for file_path in list_of_photo_paths:
            logger.info(f"Photo appears: {file_path}")
            # 2. Sync Hashing
            file_hash = generate_file_hash(file_path)
            logger.info(f"File hash: {file_hash}")
            # 3. Get File System creation time (Sync Proxy)
            stat = os.stat(file_path)
            file_created_at = datetime.fromtimestamp(
                getattr(stat, 'st_birthtime', stat.st_ctime)
            )
            logger.info(f"File created at: {file_created_at}")
            # 4. Sync DB Check & Registration (Atomic)
            try:
                photo = check_photo_hash_exists(db, file_hash)
                if photo:
                    logger.info(f"Photo {file_path} already exists in DB")
                    update_folder_scanner_progress(db, folder_scanner.id)
                    db.commit()
                    db.refresh(folder_scanner)
                    
                    logger.info(f"Folder scanner scanned_steps: {folder_scanner.scanned_steps}")
                    continue
                photo = create_photo_record(db, file_hash, file_path, file_created_at)
                logger.info(f"Photo {file_path} created in DB with ID: {photo.id}")
                start_pipeline(photo.id, folder_scanner.id)
                logger.debug(f"Pipeline started for photo {photo.id}")
            except Exception as e:
                logger.error(f"Error starting pipeline for photo {photo.id}: {e}")
                db.rollback()
                db.close()
                return False
        db.close()
        return True
    else:
        total_steps = 0
        logger.error(f"Folder '{path}' does not exist")
        db.close()
        return False


def start_existing_folder_scanners():
    db = SessionLocal()
    folder_scanners = db.query(FolderScanner).all()
    for folder_scanner in folder_scanners:
        if folder_scanner.scanned_steps < folder_scanner.total_steps:
            logger.info(f"Folder scanner with ID {folder_scanner.id} is active")
            start_folder_scanner_task(folder_scanner.path)
        else:
            logger.info(f"Folder scanner with ID {folder_scanner.id} is done")
            delete_folder_scanner(db, folder_scanner.id)
    db.close()