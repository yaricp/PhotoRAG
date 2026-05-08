from src.observer import start_observer
from src.db_service import (
    get_all_active_watchers, 
    update_watcher_status,
    get_or_create_watcher,
    get_all_watchers,
    delete_watcher
)
from loguru import logger


class WatcherService:
    def __init__(self):
        self.active: list[dict] = []

    def start_all(self, db):
        logger.info("Starting all watchers...")
        watchers = get_all_watchers(db)
        logger.info(f"Found {len(watchers)} watchers")

        for watcher in watchers:
            logger.info(f"Starting watcher for path: {watcher.path}")
            self.active.append({
                "id": watcher.id,
                "path": watcher.path,
                "observer": self._start_observer(
                    watcher.path,
                    watcher.destination_path
                )
            })
            watcher_db = update_watcher_status(db, watcher.id, "active")
            logger.info(f"Watcher {watcher.id} started")
        logger.info(f"All watchers started")
        return {"message": "watchers started"}

    def start_watcher(self, db, path: str, destination_path: str) -> dict:
        logger.info(f"Starting watcher for path: {path}")
        watcher_db = get_or_create_watcher(db, path, destination_path)
        if watcher_db.status == "active":
            logger.info(f"Watcher for path {path} is already active")
            return watcher_db
        new_watcher = {
            "id": watcher_db.id,
            "path": watcher_db.path,
            "observer": self._start_observer(
                watcher_db.path,
                watcher_db.destination_path
            )
        }
        self.active.append(new_watcher)
        watcher_db = update_watcher_status(db, watcher_db.id, "active")
        logger.info(f"Watcher started for path: {path}")
        return {"status": "watching", "target": path, "id": watcher_db.id}

    def _start_observer(self, path: str, destination_path: str):
        logger.info(f"Starting observer for path: {path}")
        observer = start_observer(path, destination_path)
        logger.info(f"Observer started: {observer}")
        return observer
        
    def stop_all(self, db):
        logger.info("Stopping all watchers...")
        for active in self.active:
            active["observer"].stop()
            active["observer"].join()
            update_watcher_status(db, active["id"], "inactive")
            logger.info(f"Stopped watcher for path: {active['path']}")
        self.active.clear()
        logger.info("All watchers stopped")

    def stop_watcher(self, watcher_id: int, db):
        logger.info(f"Stopping watcher: {watcher_id}")
        logger.info(f"Active watchers: {self.active}")
        watcher = list(filter(
            lambda w: w["id"] == watcher_id, self.active
        ))[0]
        logger.info(f"Stopping watcher for path: {watcher}")
        watcher["observer"].stop()
        watcher["observer"].join()
        del_watcher = delete_watcher(db, watcher["id"])
        logger.info(f"Stopped watcher for path: {watcher['path']}")
        return del_watcher