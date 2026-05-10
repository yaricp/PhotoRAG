from fastapi import FastAPI, Depends, HTTPException, Query
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from typing import List, Dict, Any, Optional
from loguru import logger
from contextlib import asynccontextmanager

from src.db_service import (
    get_all_model_states,
    get_photo_by_id,
    get_all_photos,
    get_available_dates,
    get_photos_by_vector,
    get_all_watchers,
    get_all_tags,
    get_all_categories,
    get_all_cameras,
    get_all_geopositions,
    delete_photo,
    get_job_by_photo_id,
    get_all_jobs,
    get_or_create_folder_scanner,
    update_folder_scanner_progress,
    get_all_folder_scanners,
    delete_folder_scanner,
    get_all_model_configs,
    get_model_config,
    update_model_config,
    get_duplicate_groups,
    archive_photo,
    delete_duplicate_record,
    get_quality_summary,
    get_photos_by_issue_type,
    get_all_settings,
    set_setting,
    get_history_actions,
    perform_undo,
)
from src.database import Session, SessionLocal
from src.deps import get_db, get_translator
from src.config import Api_Settings
from src.models import Photo, Category, Tag, Camera, Geoposition, PhotoDuplicate
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
    Job as JobSchema,
    FolderScannerProgress as FolderScannerProgressSchema,
    FolderScanner as FolderScannerSchema,
    FolderScannerRequest,
    AIModelConfigResponse,
    AIModelConfigUpdate,
    AppSettingSchema,
    HistoryActionSchema,
)
from src.ai.translator import Translator
from src.ai.registry import registry
from src.watcher_service import WatcherService
from src.graphs.ai_agent import app as agent_app
from langchain_core.messages import HumanMessage
from src.tasks.folder_scanners import start_folder_scanner_task


watcher_service = WatcherService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    # load models in memory
    registry.translator.load()
    registry.vision_generator.load()
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


@app.post("/api/watchers/", tags=["Watchers"])
def trigger_directory_watch_endpoint(request: WatchRequest, db: Session = Depends(get_db)):
    logger.info(f"Received watch request for path: {request.path}")
    watcher = watcher_service.start_watcher(db, request.path, request.destination_path)
    return watcher


@app.get("/api/watchers/", tags=["Watchers"], response_model=List[Watcher])
def get_watchers_endpoint(db: Session = Depends(get_db)) -> List[Watcher]:
    logger.info("Getting watchers")
    watchers = get_all_watchers(db)
    logger.info(f"Watchers found in DB: {watchers}")
    return watchers


@app.delete("/api/watchers/{watcher_id}", tags=["Watchers"])
def delete_watcher_endpoint(watcher_id: int, db: Session = Depends(get_db)) -> None:
    logger.info(f"Deleting watcher: {watcher_id}")
    del_watcher = watcher_service.stop_watcher(watcher_id, db)
    return del_watcher

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
    skip: int = Query(0, alias="skip"),
    limit: int = Query(50, alias="limit"),
    sort_by: str = Query("created_at", alias="sort_by"),
    sort_order: str = Query("desc", alias="sort_order"),
    category_ids: Optional[list[int]] = Query(None, alias="category_ids"),
    tag_ids: Optional[list[int]] = Query(None, alias="tag_ids"),
    camera_id: Optional[int] = Query(None, alias="camera_id"),
    geoposition_id: Optional[int] = Query(None, alias="geoposition_id"),
    is_doc: Optional[bool] = Query(None, alias="is_doc"),
    year: Optional[int] = Query(None, alias="year"),
    month: Optional[int] = Query(None, alias="month"),
    day: Optional[int] = Query(None, alias="day"),
    db: Session = Depends(get_db)
) -> PaginatedResponse[PhotoSchema]:
    logger.info("Getting all photos")
    photos, total = get_all_photos(
        db, skip=skip, limit=limit, sort_by=sort_by, sort_order=sort_order,
        category_ids=category_ids, tag_ids=tag_ids, camera_id=camera_id,
        geoposition_id=geoposition_id, is_doc=is_doc,
        year=year, month=month, day=day,
    )
    return PaginatedResponse(
        items=photos,
        total=total,
        page=(skip // limit) + 1 if limit > 0 else 1,
        size=limit
    )


@app.get("/api/photos/available-dates/", tags=["Photos"])
def get_available_dates_endpoint(
    category_ids: Optional[list[int]] = Query(None),
    tag_ids: Optional[list[int]] = Query(None),
    camera_id: Optional[int] = Query(None),
    geoposition_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
) -> List[Dict[str, int]]:
    return get_available_dates(
        db,
        category_ids=category_ids,
        tag_ids=tag_ids,
        camera_id=camera_id,
        geoposition_id=geoposition_id,
    )


@app.get("/api/duplicates/", tags=["Photos"])
def get_duplicates_endpoint(db: Session = Depends(get_db)) -> dict:
    return get_duplicate_groups(db)


@app.post("/api/photos/{photo_id}/archive", tags=["Photos"])
def archive_photo_endpoint(photo_id: int, db: Session = Depends(get_db)) -> dict:
    photo = archive_photo(db, photo_id)
    if not photo:
        raise HTTPException(status_code=404)
    return {"id": photo.id, "is_archived": photo.is_archived}


@app.delete("/api/duplicates/{record_id}", tags=["Photos"])
def delete_duplicate_record_endpoint(record_id: int, db: Session = Depends(get_db)) -> dict:
    import os
    record = db.query(PhotoDuplicate).filter_by(id=record_id).first()
    if not record:
        raise HTTPException(status_code=404)
    if record.match_type == "exact" and record.duplicate_file_path:
        if os.path.exists(record.duplicate_file_path):
            os.remove(record.duplicate_file_path)
            logger.info(f"Deleted duplicate file from disk: {record.duplicate_file_path}")
    deleted = delete_duplicate_record(db, record_id)
    return {"id": record_id}


@app.get("/api/garbage/", tags=["Garbage"])
def get_garbage_summary_endpoint(db: Session = Depends(get_db)) -> dict:
    return {"counts": get_quality_summary(db)}


@app.get("/api/garbage/{issue_type}/photos/", tags=["Garbage"])
def get_garbage_photos_endpoint(
    issue_type: str,
    skip: int = Query(0),
    limit: int = Query(20),
    db: Session = Depends(get_db),
) -> PaginatedResponse[PhotoSchema]:
    photos, total = get_photos_by_issue_type(db, issue_type, skip=skip, limit=limit)
    return PaginatedResponse(
        items=photos,
        total=total,
        page=(skip // limit) + 1 if limit > 0 else 1,
        size=limit,
    )


@app.delete("/api/photos/{photo_id}", tags=["Photos"], response_model=PhotoSchema)
def delete_photo_endpoint(photo_id: int, db: Session = Depends(get_db)) -> PhotoSchema:
    import os
    photo = get_photo_by_id(db, photo_id)
    if not photo:
        raise HTTPException(status_code=404)
    file_path = photo.file_path
    deleted_photo = delete_photo(db, photo_id)
    if not deleted_photo:
        raise HTTPException(status_code=404)
    if file_path and os.path.exists(file_path):
        os.remove(file_path)
        logger.info(f"Deleted file from disk: {file_path}")
    return deleted_photo


@app.post("/api/search/", tags=["Photos"], response_model=List[PhotoSchema])
async def search_photos_endpoint(
    request: QueryRequest,
    db: Session = Depends(get_db),
    translator: Optional[Translator] = Depends(get_translator)
) -> List[PhotoSchema]:
    """Search photos by vector"""
    logger.info(f"Received search request for text: {request.text_query}")
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
    logger.info(f"Agent result: {result}")
    # Get the last AI message
    last_msg = result["messages"][-1]
    
    return ChatResponse(
        response=last_msg.content,
        photos=result["photos"]
    )


@app.get("/api/jobs/", tags=["Jobs"], response_model=List[JobSchema])
def get_jobs_endpoint(db: Session = Depends(get_db)) -> List[JobSchema]:
    """Get all jobs"""
    results = get_all_jobs(db)
    logger.info(f"Jobs found in DB: {results}")
    output = []
    for res in results:
        logger.info(f"Job found in DB: {res}")
        output.append(
            JobSchema(
                id=res.id,
                updated_at=res.updated_at,
                created_at=res.created_at,
                photo_id=res.photo_id,
                phase=res.phase,
                tasks=res.tasks,
                file_path=res.photo.file_path
            )
        )

    logger.info(f"Jobs translated: {output}")
    return output


@app.get("/api/jobs/{photo_id}", tags=["Jobs"], response_model=JobSchema)
def get_job_endpoint(photo_id: int, db: Session = Depends(get_db)) -> JobSchema:
    """Get job status for a photo"""
    job = get_job_by_photo_id(db, photo_id)

    return job


@app.get(
    "/api/folder_scanners/progress/",
    tags=["Folder Scanners"],
    response_model=List[FolderScannerProgressSchema]
)
def get_folder_scanners_progress_endpoint(
    db: Session = Depends(get_db)
) -> List[FolderScannerProgressSchema]:
    """Get all folder scanners"""
    folders = get_all_folder_scanners(db)
    logger.info(f"Folders found in DB: {folders}")
    output = []
    for folder in folders:
        # if folder.scanned_steps == folder.total_steps:
        #     delete_folder_scanner(db, folder.id)
        #     continue
        progress = int((folder.scanned_steps / folder.total_steps)*100)
        logger.info(f"Folder {folder.id} progress: {progress}")
        output.append(
            FolderScannerProgressSchema(
                id=folder.id,
                path=folder.path,
                progress=progress
            )
        )
    return output


@app.get(
    "/api/folder_scanners/",
    tags=["Folder Scanners"],
    response_model=List[FolderScannerSchema]
)
def get_folder_scanners_endpoint(
    db: Session = Depends(get_db)
) -> List[FolderScannerSchema]:
    """Get all folder scanners"""
    folders = get_all_folder_scanners(db)
    return folders


@app.post("/api/folder_scanners/", tags=["Folder Scanners"])
def start_folder_scanner_endpoint(request: FolderScannerRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    """Start a new folder scanner"""
    result = start_folder_scanner_task(request.path)
    if result:
        return {"status": "started"}
    else:
        raise HTTPException(status_code=400, detail="Folder scanner could not be started")


@app.delete("/api/folder_scanners/{folder_scanner_id}", tags=["Folder Scanners"])
def delete_folder_scanner_endpoint(folder_scanner_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    """Delete a folder scanner"""
    result = delete_folder_scanner(db, folder_scanner_id)
    if result:
        return FolderScannerSchema(
            id=result.id,
            path=result.path,
            progress=100
        )
    else:
        raise HTTPException(status_code=400, detail="Folder scanner could not be deleted")


@app.get("/api/models/", tags=["Models"], response_model=List[AIModelConfigResponse])
def get_all_models_endpoint(db: Session = Depends(get_db)):
    """Get all AI model configurations"""
    return get_all_model_configs(db)


@app.put("/api/models/{config_type}", tags=["Models"], response_model=AIModelConfigResponse)
def update_model_endpoint(
    config_type: str,
    request: AIModelConfigUpdate,
    db: Session = Depends(get_db)
):
    """Update AI model configuration and reload it in the registry"""
    config = update_model_config(db, config_type, request)
    if not config:
        raise HTTPException(status_code=404, detail="Model config not found")

    # Invalidate cache so it reloads with new settings
    registry.reset_model(config_type)
    return config


# ---------------------------------------------------------------------------
# Settings endpoints
# ---------------------------------------------------------------------------

class SettingUpdateRequest(BaseModel):
    value: str


@app.get("/api/settings/", tags=["Settings"])
def get_settings_endpoint(db: Session = Depends(get_db)) -> Dict[str, str]:
    return get_all_settings(db)


@app.put("/api/settings/{key}", tags=["Settings"], response_model=AppSettingSchema)
def update_setting_endpoint(
    key: str,
    request: SettingUpdateRequest,
    db: Session = Depends(get_db),
) -> AppSettingSchema:
    setting = set_setting(db, key, request.value)
    return AppSettingSchema(key=setting.key, value=setting.value)


# ---------------------------------------------------------------------------
# History endpoints
# ---------------------------------------------------------------------------

@app.get("/api/history/", tags=["History"], response_model=List[HistoryActionSchema])
def get_history_endpoint(db: Session = Depends(get_db)) -> List[HistoryActionSchema]:
    actions = get_history_actions(db, limit=20)
    return [HistoryActionSchema.from_orm_model(a) for a in actions]


@app.post("/api/history/undo/", tags=["History"])
def undo_last_action_endpoint(db: Session = Depends(get_db)) -> Dict[str, str]:
    detail = perform_undo(db)
    return {"status": "ok", "detail": detail}
