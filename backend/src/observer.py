import asyncio
import os
import threading
from datetime import datetime

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from loguru import logger

from src.utils import generate_file_hash, move_photo, get_photo_capture_date
from src.incoming_pipeline import start_pipeline
from src.db.database import SessionLocal
from src.db_service import check_photo_hash_exists, create_photo_record, record_exact_duplicate


class PhotoEventHandler(FileSystemEventHandler):
    """
    Watches a folder for new photo files and submits them to the async pipeline.

    A dedicated asyncio event loop runs in a daemon thread so that multiple
    photos arriving close together are processed concurrently rather than
    queued behind each other.
    """

    def __init__(self, destination_root_folder: str):
        super().__init__()
        self.destination_root_folder = destination_root_folder
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._loop.run_forever,
            daemon=True,
            name="observer-event-loop",
        )
        self._thread.start()

    def on_created(self, event):
        if event.is_directory:
            return
        src = event.src_path
        if not src.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.tiff')):
            return

        logger.info(f"[observer] New file: {src}")
        try:
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

            # Submit the async pipeline to the dedicated event loop without blocking
            # the watchdog thread.  Multiple photos arriving simultaneously each get
            # their own coroutine on the shared loop and run concurrently.
            logger.info(f"[observer] Submitting pipeline for photo_id={photo_id}")
            asyncio.run_coroutine_threadsafe(
                start_pipeline(photo_id),
                self._loop,
            )

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
