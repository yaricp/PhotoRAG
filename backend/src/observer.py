from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from src.watcher import generate_file_hash
from src.tasks import process_photo_task

class PhotoEventHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory and event.src_path.lower().endswith(('.jpg', '.png', '.jpeg')):
            # Tier 1: Immediate Hashing
            # Note: In a real app, we should wait slightly for the file download/copy to complete
            # or check if the file is closed.
            try:
                file_hash = generate_file_hash(event.src_path)
                # Tier 2: Queue for AI
                process_photo_task(event.src_path)
            except Exception as e:
                print(f"Error processing {event.src_path}: {e}")

def start_observer(path: str):
    observer = Observer()
    observer.schedule(PhotoEventHandler(), path, recursive=False)
    observer.start()
    return observer
