from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from src.watcher import generate_file_hash
from src.tasks import metadata_task, clip_task, vision_task, ocr_task
from src.database import SessionLocal
from src.db_service import check_photo_hash_exists

class PhotoEventHandler(FileSystemEventHandler):
    def on_created(self, event):
        # 1. Sync Extension Check
        if not event.is_directory and event.src_path.lower().endswith(('.jpg', '.png', '.jpeg', '.gif', '.tiff')):
            try:
                # 2. Sync Hashing
                file_hash = generate_file_hash(event.src_path)
                
                # 3. Sync DB Check
                db = SessionLocal()
                try:
                    photo = check_photo_hash_exists(db, file_hash)
                    if not photo:
                        # 4. Dispatch 4 Parallel Async Tasks
                        metadata_task(event.src_path)
                        clip_task(event.src_path)
                        vision_task(event.src_path)
                        ocr_task(event.src_path)
                finally:
                    db.close()
                    
            except Exception as e:
                print(f"Error processing {event.src_path}: {e}")

def start_observer(path: str):
    observer = Observer()
    observer.schedule(PhotoEventHandler(), path, recursive=False)
    observer.start()
    return observer
