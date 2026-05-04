from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from typing import List, Dict, Any, Optional
from loguru import logger
from contextlib import asynccontextmanager

from src.db_service import (
    get_all_model_states,
    get_photo_by_id,
    get_all_photos,
    get_photos_by_vector,
    get_all_watchers,
    get_all_tags,
    get_all_categories,
    get_all_cameras,
    get_all_geopositions,
    delete_photo,
    get_job_by_photo_id
)
from src.database import Session, SessionLocal
from src.deps import get_db, get_translator
from src.config import Api_Settings
from src.models import Photo, Category, Tag, Camera, Geoposition
from src.schemas import (
    Photo as PhotoSchema,
    WatchRequest,
    QueryRequest,
    Watcher,
    PaginatedResponse,
    Tag as TagSchema,
    Category as CategorySchema,
    Camera as CameraSchema,
    GeoPosition as GeoPositionSchema,
    TranslateRequest,
    ChatRequest,
    ChatResponse,
    Job as JobSchema
)
from src.ai.translator import Translator
from src.ai.registry import registry
from src.watcher_service import WatcherService
from src.graphs.ai_agent import app as agent_app
from langchain_core.messages import HumanMessage


watcher_service = WatcherService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    registry.translator.load()
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


@app.get("/api/system/status/", tags=["System"])
def get_system_status_endpoint(db: Session = Depends(get_db)):
    logger.info("Getting system status")
    states = get_all_model_states(db)
    logger.info(f"System status: {states}")
    return {
        "ready": all(s.status == "ready" for s in states),
        "models": [{"name": s.name, "status": s.status} for s in states]
    }


@app.post("/api/watch/", tags=["Watchers"])
def trigger_directory_watch_endpoint(request: WatchRequest, db: Session = Depends(get_db)):
    logger.info(f"Received watch request for path: {request.path}")
    watcher = watcher_service.start_watcher(request.path, db)
    return watcher


@app.get("/api/watchers/", tags=["Watchers"], response_model=List[Watcher])
def get_watchers_endpoint(db: Session = Depends(get_db)) -> List[Watcher]:
    logger.info("Getting watchers")
    watchers = get_all_watchers(db)
    logger.info(f"Watchers found in DB: {watchers}")
    return watchers


@app.get("/api/stream/")
def sse_event_stream_endpoint():
    # Will yield Async generator for SSE UI updates
    return {"status": "stream_placeholder"}


@app.get("/api/photos/{photo_id}", tags=["Photos"], response_model=PhotoSchema)
def get_photo_endpoint(
    photo_id: int,
    db: Session = Depends(get_db),
    translator: Optional[Translator] = Depends(get_translator)
) -> PhotoSchema:
    logger.info(f"Getting photo: {photo_id}")
    photo = get_photo_by_id(db, photo_id)
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    logger.info(f"Photo found in DB: {photo}")
    return photo


@app.get("/api/photos/", tags=["Photos"], response_model=PaginatedResponse[PhotoSchema])
def get_photos_endpoint(
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    category_id: Optional[int] = None,
    tag_id: Optional[int] = None,
    camera_id: Optional[int] = None,
    is_doc: Optional[bool] = None,
    db: Session = Depends(get_db),
    translator: Optional[Translator] = Depends(get_translator)
) -> PaginatedResponse[PhotoSchema]:
    logger.info("Getting all photos")
    photos, total = get_all_photos(
        db, skip=skip, limit=limit, sort_by=sort_by, sort_order=sort_order,
        category_id=category_id, tag_id=tag_id, camera_id=camera_id, is_doc=is_doc
    )
    return PaginatedResponse(
        items=photos,
        total=total,
        page=(skip // limit) + 1 if limit > 0 else 1,
        size=limit
    )


@app.delete("/api/photos/{photo_id}", tags=["Photos"], response_model=PhotoSchema)
def delete_photo_endpoint(photo_id: int, db: Session = Depends(get_db)) -> PhotoSchema:
    deleted_photo = delete_photo(db, photo_id)
    if not deleted_photo:
        raise HTTPException(status_code=404)
    return deleted_photo


@app.post("/api/search/", tags=["Photos"], response_model=List[PhotoSchema])
async def search_photos_endpoint(
    request: QueryRequest,
    db: Session = Depends(get_db),
    translator: Optional[Translator] = Depends(get_translator)
) -> List[PhotoSchema]:
    """Search photos by vector"""
    logger.info(f"Received search request for text: {request.text_query}")
    request.text_query = translator.translate(request.text_query, backward=True)
    photos = get_photos_by_vector(db, request.text_query, request.k)
    return photos


@app.get("/api/tags/", tags=["Metadata"], response_model=List[TagSchema])
def get_tags_endpoint(db: Session = Depends(get_db)) -> List[TagSchema]:
    return get_all_tags(db)


@app.get("/api/categories/", tags=["Metadata"], response_model=List[CategorySchema])
def get_categories_endpoint(db: Session = Depends(get_db)) -> List[CategorySchema]:
    return get_all_categories(db)


@app.get("/api/cameras/", tags=["Metadata"], response_model=List[CameraSchema])
def get_cameras_endpoint(db: Session = Depends(get_db)) -> List[CameraSchema]:
    return get_all_cameras(db)


@app.get("/api/geopositions/", tags=["Metadata"], response_model=List[GeoPositionSchema])
def get_geopositions_endpoint(db: Session = Depends(get_db)) -> List[GeoPositionSchema]:
    return get_all_geopositions(db)


@app.post("/api/chat/", tags=["Agent"], response_model=ChatResponse)
async def chat_with_agent_endpoint(request: ChatRequest) -> ChatResponse:
    """Chat with the AI photo assistant"""
    logger.info(f"Received chat message: {request.message} (thread_id: {request.thread_id})")
    
    config = {"configurable": {"thread_id": request.thread_id}}
    inputs = {"messages": [HumanMessage(content=request.message)]}
    
    # Run the agent graph
    result = await agent_app.ainvoke(inputs, config)
    
    # Get the last AI message
    last_msg = result["messages"][-1]
    
    return ChatResponse(
        response=last_msg.content,
        thread_id=request.thread_id
    )


@app.get("/api/job/{photo_id}", tags=["Jobs"], response_model=JobSchema)
def get_job_endpoint(photo_id: int, db: Session = Depends(get_db)) -> JobSchema:
    """Get job status for a photo"""
    job = get_job_by_photo_id(db, photo_id)
    return job