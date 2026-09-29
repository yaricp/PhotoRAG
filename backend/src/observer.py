import os
import time

from loguru import logger
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from src.db.database import SessionLocal
from src.db_service import (
    check_photo_hash_exists,
    create_photo_record,
    record_exact_duplicate,
)
from src.pipeline_queue import enqueue_photo_run
from src.utils import generate_file_hash, get_photo_capture_date, move_photo

FILE_READY_ATTEMPTS = 60
FILE_READY_DELAY_SECONDS = 0.5


def wait_until_file_ready(
    path: str,
    attempts: int = FILE_READY_ATTEMPTS,
    delay_seconds: float = FILE_READY_DELAY_SECONDS,
) -> bool:
    """
    Wait until a newly-created file can be read and its size is stable.

    Windows and sync providers such as OneDrive can emit a created event while
    the file is still locked, being copied, or being hydrated locally. Trying to
    hash or move it immediately raises PermissionError and drops the photo.
    """
    last_size: int | None = None
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            size = os.path.getsize(path)
            with open(path, "rb") as file:
                file.read(1)

            if last_size == size:
                if attempt > 1:
                    logger.info(f"[observer] File is ready after {attempt} checks: {path}")
                return True

            last_size = size
        except (OSError, PermissionError) as exc:
            last_error = exc
            if attempt == 1 or attempt == attempts or attempt % 10 == 0:
                logger.info(f"[observer] Waiting for file to become readable: {path} ({exc})")

        time.sleep(delay_seconds)

    detail = f": {last_error}" if last_error else ""
    logger.error(f"[observer] File was not ready after {attempts} checks: {path}{detail}")
    return False


class PhotoEventHandler(FileSystemEventHandler):
    """Watch new files and persist work for the shared backend scheduler."""

    def __init__(self, destination_root_folder: str):
        super().__init__()
        self.destination_root_folder = destination_root_folder

    def on_created(self, event):
        if event.is_directory:
            return
        src = event.src_path
        if not src.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".tiff")):
            return

        logger.info(f"[observer] New file: {src}")
        try:
            if not wait_until_file_ready(src):
                return

            file_hash = generate_file_hash(src)

            db = SessionLocal()
            try:
                existing = check_photo_hash_exists(db, file_hash)
                if existing:
                    logger.info(f"[observer] Exact duplicate: {src}")
                    record_exact_duplicate(db, existing.id, src)
                    db.commit()
                    return

                capture_date = get_photo_capture_date(src)
                new_path = move_photo(src, self.destination_root_folder)
                logger.info(f"[observer] Moved to: {new_path}")

                photo_id = None
                try:
                    photo = create_photo_record(db, file_hash, new_path, capture_date)
                    db.flush()
                    photo_id = photo.id
                    db.commit()
                except Exception as exc:
                    logger.error(f"[observer] Failed to create photo record for {new_path}: {exc}")
                    db.rollback()
                    return

            finally:
                db.close()

            if photo_id is None:
                return

            logger.info(f"[observer] Queuing pipeline for photo_id={photo_id}")
            enqueue_photo_run(photo_id, "watcher")

        except Exception as exc:
            logger.error(f"[observer] Error processing {src}: {exc}")


def start_observer(path: str, destination_root_folder: str) -> Observer:
    """Start a watchdog observer for *path*, moving new photos to *destination_root_folder*."""
    logger.info(f"[observer] Starting observer for: {path}")
    observer = Observer()
    observer.schedule(
        PhotoEventHandler(destination_root_folder),
        path,
        recursive=False,
    )
    observer.start()
    logger.info(f"[observer] Observer running: {observer}")
    return observer
