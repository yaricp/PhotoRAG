from fastapi import FastAPI, Depends, HTTPException

from typing import List, Dict, Any
from loguru import logger
from contextlib import asynccontextmanager

from src.db_service import (
    get_all_model_states,
    get_photo_by_id,
    get_all_photos,
    get_photos_by_vector
)
from src.database import get_db, Session, SessionLocal
from src.config import Api_Settings
from src.models import Photo
from src.schemas import (
    Photo as PhotoSchema,
    WatchRequest,
    QueryRequest
)
from src.watcher_service import WatcherService


watcher_service = WatcherService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    # startup
    watcher_service.start_all(db)
    yield
    # shutdown
    watcher_service.stop_all(db)
    db.close()


app = FastAPI(
    title="Photo Describer MVP",
    description="AI photo analyzer that detects objects, locations, and generates descriptions.",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/api/system/status/")
def get_system_status():
    logger.info("Getting system status")
    db = SessionLocal()
    try:
        states = get_all_model_states(db)
        logger.info(f"System status: {states}")
        return {
            "ready": all(s.status == "ready" for s in states),
            "models": [{"name": s.name, "status": s.status} for s in states]
        }
    finally:
        db.close()


@app.post("/api/watch/")
def trigger_directory_watch(request: WatchRequest, db: Session = Depends(get_db)):
    logger.info(f"Received watch request for path: {request.path}")
    watcher = watcher_service.start_watcher(request.path, db)
    return watcher


@app.get("/api/stream/")
def sse_event_stream():
    # Will yield Async generator for SSE UI updates
    return {"status": "stream_placeholder"}


@app.get("/api/photos/{photo_id}", response_model=PhotoSchema)
def get_photo(photo_id: int, db: Session = Depends(get_db)) -> PhotoSchema:
    logger.info(f"Getting photo: {photo_id}")
    photo = get_photo_by_id(db, photo_id)
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    logger.info(f"Photo found in DB: {photo}")
    return photo


@app.get("/api/photos/", tags=["Photos"], response_model=List[PhotoSchema])
def get_photos(db: Session = Depends(get_db)) -> List[PhotoSchema]:
    logger.info("Getting all photos")
    photos = get_all_photos(db)
    logger.info(f"Photos found in DB: {photos}")
    return photos


@app.post("/api/search/", response_model=List[PhotoSchema])
async def search_photos(
    request: QueryRequest,
    db: Session = Depends(get_db)
):
    """Search photos by vector"""
    logger.info(f"Received search request for text: {request.text_query}")
    photos = get_photos_by_vector(db, request.text_query, request.k)
    logger.info(f"Found photos: {photos}")
    return photos
