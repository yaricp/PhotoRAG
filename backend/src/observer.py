import os
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from loguru import logger

from src.utils import generate_file_hash
from src.tasks import start_pipeline
from src.database import SessionLocal
from src.db_service import check_photo_hash_exists, create_photo_record



class PhotoEventHandler(FileSystemEventHandler):
    def on_created(self, event):
        # 1. Sync Extension Check
        if not event.is_directory and event.src_path.lower().endswith(('.jpg', '.png', '.jpeg', '.gif', '.tiff')):
            try:
                logger.info(f"Photo created: {event.src_path}")
                # 2. Sync Hashing
                file_hash = generate_file_hash(event.src_path)
                logger.info(f"File hash: {file_hash}")
                # 3. Get File System creation time (Sync Proxy)
                stat = os.stat(event.src_path)
                file_created_at = datetime.fromtimestamp(getattr(stat, 'st_birthtime', stat.st_ctime))
                logger.info(f"File created at: {file_created_at}")
                # 4. Sync DB Check & Registration (Atomic)
                db = SessionLocal()
                try:
                    photo = check_photo_hash_exists(db, file_hash)
                    logger.info(f"Photo found in DB: {photo}")
                    if not photo:
                        logger.info(f"Photo not found in DB")
                        # 5. Sync Create Record with file_created_at
                        try:
                            photo = create_photo_record(db, file_hash, event.src_path, file_created_at)
                            logger.info(f"Photo created: {photo}")
                        except Exception as e:
                            logger.error(f"Error creating photo record for photo {event.src_path}: {e}")
                            return
                        # 6. Dispatch Async Tasks with the Photo ID
                        logger.info(f"Starting pipeline for photo: {photo.id}")
                        try:
                            start_pipeline(photo.id)
                        except Exception as e:
                            logger.error(f"Error starting pipeline for photo {photo.id}: {e}")
                except Exception as e:
                    logger.error(f"Error dispatching tasks for photo {photo.id}: {e}")
                    return
                finally:
                    db.close()
                    logger.info(f"working with {event.src_path} is finished")
                    
            except Exception as e:
                logger.error(f"Error processing {event.src_path}: {e}")


def start_observer(path: str):
    """
    Starts the observer for the given path.
    """
    logger.info(f"Starting observer for path: {path}")
    observer = Observer()
    observer.schedule(PhotoEventHandler(), path, recursive=False)
    observer.start()
    logger.info(f"Observer: {observer}")
    return observer
