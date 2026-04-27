import os
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from src.watcher import generate_file_hash
from src.tasks import metadata_task, auto_tag_clip_task, categorize_photo_task, vision_task, ocr_task
from src.database import SessionLocal
from src.db_service import check_photo_hash_exists, create_photo_record


class PhotoEventHandler(FileSystemEventHandler):
    def on_created(self, event):
        # 1. Sync Extension Check
        if not event.is_directory and event.src_path.lower().endswith(('.jpg', '.png', '.jpeg', '.gif', '.tiff')):
            try:
                # 2. Sync Hashing
                file_hash = generate_file_hash(event.src_path)
                
                # 3. Get File System creation time (Sync Proxy)
                stat = os.stat(event.src_path)
                file_created_at = datetime.fromtimestamp(getattr(stat, 'st_birthtime', stat.st_ctime))
                
                # 4. Sync DB Check & Registration (Atomic)
                db = SessionLocal()
                try:
                    photo = check_photo_hash_exists(db, file_hash)
                    if not photo:
                        # 5. Sync Create Record with file_created_at
                        photo = create_photo_record(db, file_hash, event.src_path, file_created_at)
                        
                        # 6. Dispatch Async Tasks with the Photo ID
                        metadata_task(photo.id)
                        auto_tag_clip_task(photo.id)
                        categorize_photo_task(photo.id)
                        vision_task(photo.id)
                        ocr_task(photo.id)
                finally:
                    db.close()
                    
            except Exception as e:
                print(f"Error processing {event.src_path}: {e}")


def start_observer(path: str):
    observer = Observer()
    observer.schedule(PhotoEventHandler(), path, recursive=False)
    observer.start()
    return observer
