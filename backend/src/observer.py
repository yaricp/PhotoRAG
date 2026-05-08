import os
import shutil
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from loguru import logger

from src.utils import (
    generate_file_hash, move_photo, get_photo_capture_date
)
from src.tasks import start_pipeline
from src.database import SessionLocal
from src.db_service import check_photo_hash_exists, create_photo_record



class PhotoEventHandler(FileSystemEventHandler):
    """
    Observes the given path for new photo files.
    """

    def __init__(self, destination_root_folder: str):
        self.destination_root_folder = destination_root_folder

    def on_created(self, event):
        # 1. Sync Extension Check
        if not event.is_directory and event.src_path.lower().endswith(('.jpg', '.png', '.jpeg', '.gif', '.tiff')):
            try:
                logger.info(f"Photo appears: {event.src_path}")
                # 2. Sync Hashing
                file_hash = generate_file_hash(event.src_path)
                logger.info(f"File hash: {file_hash}")
                
                db = SessionLocal()
                try:
                    photo = check_photo_hash_exists(db, file_hash)
                    logger.info(f"Photo found in DB: {photo}")
                    if not photo:
                        logger.info(f"Photo not found in DB")
                        photo_capture_date = get_photo_capture_date(event.src_path)
                        logger.info(f"Photo capture date: {photo_capture_date}")
                        new_path = move_photo(event.src_path, self.destination_root_folder)
                        logger.info(f"File moved to: {new_path}")
                        try:
                            photo = create_photo_record(
                                db, file_hash, new_path, photo_capture_date
                            )
                            logger.info(f"Photo created: {photo}")
                        except Exception as e:
                            logger.error(f"Error creating photo record for photo {new_path}: {e}")
                            return
                        # 6. Dispatch Async Tasks with the Photo ID
                        logger.info(f"Starting pipeline for photo: {photo.id}")
                        try:
                            start_pipeline(photo.id)
                        except Exception as e:
                            logger.error(f"Error starting pipeline for photo {photo.id}: {e}")
                except Exception as e:
                    logger.error(f"Error dispatching tasks for file {event.src_path}: {e}")
                    return
                finally:
                    db.close()
                    logger.info(f"working with {event.src_path} is finished")
                    
            except Exception as e:
                logger.error(f"Error processing {event.src_path}: {e}")


def start_observer(path: str, destination_root_folder: str):
    """
    Starts the observer for the given path.
    """
    logger.info(f"Starting observer for path: {path}")
    observer = Observer()
    observer.schedule(
        PhotoEventHandler(destination_root_folder),
        path,
        recursive=False
    )
    observer.start()
    logger.info(f"Observer: {observer}")
    return observer
