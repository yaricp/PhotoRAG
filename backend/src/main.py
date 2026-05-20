from fastapi import FastAPI, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

import os
import shutil
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
    create_history_action,
    get_all_template_tags,
    get_template_tag_by_id,
    create_template_tag,
    update_template_tag,
    delete_template_tag,
    get_all_template_categories,
    get_template_category_by_id,
    create_template_category,
    update_template_category,
    delete_template_category,
    get_all_prompts,
    get_prompt_by_key,
    update_prompt,
    seed_prompts_from_json,
    get_photo_is_trash,
    mark_photo_as_trash,
    unmark_photo_as_trash,
    update_photo_fields,
    set_photo_is_doc,
    link_photo_tag,
    unlink_photo_tag,
    link_photo_category,
    unlink_photo_category,
)
from src.utils import archive_photos_to_zip
from src.db.database import Session, SessionLocal
from src.deps import get_db
from src.config import Api_Settings
from src.models import PhotoDuplicate
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
    TemplateTagCreate,
    TemplateTagUpdate,
    TemplateTagResponse,
    TemplateCategoryCreate,
    TemplateCategoryUpdate,
    TemplateCategoryResponse,
    PhotoUpdate,
    PhotoFlagsUpdate,
    PhotoTagLink,
    PhotoCategoryLink,
    PhotoTagResponse,
    PhotoCategoryResponse,
    PhotoSearchResult,
    PipelineTaskSchema,
    PromptResponse,
    PromptUpdate,
)
from src.watcher_service import WatcherService
from src.graphs.ai_agent import app as agent_app
from langchain_core.messages import HumanMessage
from src.queues.folder_scan_queue import start_folder_scanner_task
from src.task_notifier import get_notifier
from src.tasks.embedding_tasks import final_embedding_task


watcher_service = WatcherService()


@asynccontextmanager
def _eager_load_chat_model() -> None:
    """Background thread: warm up the local chat model at startup."""
    try:
        from src.ai.registry import registry as _registry
        _ = _registry.chat_model
    except Exception as exc:
        logger.error(f"[startup] Chat model warmup failed: {exc}")


async def lifespan(app: FastAPI):
    import asyncio
    import threading
    from src.pipeline_tracker import recover_interrupted_pipelines
    from src.incoming_pipeline import run_pipelines_batch

    db = SessionLocal()
    watcher_service.start_all(db)

    # Seed prompts table from prompts.json for new rows (idempotent — user edits preserved)
    try:
        from pathlib import Path
        _prompts_json = Path(__file__).parent.parent / "prompts" / "prompts.json"
        seeded = seed_prompts_from_json(db, _prompts_json)
        if seeded:
            logger.info(f"[startup] Seeded {seeded} new prompt(s) from prompts.json")
    except Exception as exc:
        logger.warning(f"[startup] Could not seed prompts (table may not exist yet — run install): {exc}")

    # Remove duplicate embedding rows — a photo should have at most one vector.
    # Duplicates accumulate when the pipeline runs more than once for the same photo
    # without the old vector being deleted first (fixed in store_photo_embedding,
    # but existing DBs may already have stale rows).
    try:
        from sqlalchemy import text as _text
        dupes_removed = db.execute(_text("""
            DELETE FROM photo_embedding_map
            WHERE id NOT IN (
                SELECT MIN(id) FROM photo_embedding_map GROUP BY photo_id
            )
        """)).rowcount
        if dupes_removed:
            db.commit()
            logger.info(f"[startup] Removed {dupes_removed} duplicate embedding map row(s)")
    except Exception as exc:
        db.rollback()
        logger.warning(f"[startup] Could not clean duplicate embedding rows: {exc}")

    # Ensure the VSS table dimension matches the configured embedding model.
    # This matters when the model was changed via the setup wizard (which writes
    # directly to the DB, bypassing the API endpoint that normally triggers a rebuild).
    try:
        from src.vector_db_services import get_embedding_dimension, current_vss_dimension, rebuild_embeddings_vss
        emb_config = get_model_config(db, "embedding")
        if emb_config:
            new_dim = get_embedding_dimension(emb_config.model_name)
            cur_dim = current_vss_dimension(db)
            if new_dim != cur_dim:
                logger.info(f"[startup] Embedding dimension mismatch {cur_dim}→{new_dim}, rebuilding VSS table")
                rebuild_embeddings_vss(db, new_dim)
    except Exception as exc:
        logger.warning(f"[startup] Could not verify embedding VSS dimension: {exc}")

    stuck_ids = recover_interrupted_pipelines(db)
    if stuck_ids:
        logger.info(f"[startup] Recovering {len(stuck_ids)} interrupted pipeline(s): {stuck_ids}")
        asyncio.create_task(run_pipelines_batch(stuck_ids))

    # Eager-load chat model in background if configured as local
    chat_config = get_model_config(db, "chat")
    chat_mode = chat_config.mode if chat_config else "local"
    if chat_mode == "local":
        logger.info("[startup] Spawning background thread to warm up local chat model")
        threading.Thread(target=_eager_load_chat_model, name="chat-warmup", daemon=True).start()

    yield

    watcher_service.stop_all(db)
    get_notifier().stop_all()
    db.close()
    from src.db.database import engine
    engine.dispose()  # closes all pooled connections → SQLite WAL checkpoints and cleans up


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

    from src.ai.registry import registry as _registry
    chat_config = get_model_config(db, "chat")
    chat_mode = chat_config.mode if chat_config else "local"
    # Remote chat model is available immediately (no warm-up); local requires the model to be loaded
    chat_ready = chat_mode == "remote" or _registry._chat_model is not None

    return {
        "ready": all(s.status == "ready" for s in states),
        "chat_ready": chat_ready,
        "models": [{"name": s.name, "status": s.status} for s in states]
    }


@app.get("/api/system/reindex-status/", tags=["System"])
def get_reindex_status_endpoint(db: Session = Depends(get_db)):
    """
    Returns whether photos need to be re-embedded.
    This happens after the embedding model changes and the VSS table is rebuilt
    (clearing photo_embedding_map).
    """
    from src.models import Photo, PhotoEmbedding
    total = db.query(Photo).filter(
        Photo.is_archived == False,
        Photo.description != None,
        Photo.description != "",
    ).count()
    indexed = db.query(PhotoEmbedding).count()
    needed = total > 0 and indexed < total
    return {"needed": needed, "total": total, "indexed": indexed}


@app.get("/api/system/tesseract/", tags=["System"])
def get_tesseract_status():
    path = shutil.which("tesseract")
    return {
        "available": path is not None,
        "path": path,
        "ocr_mode": os.environ.get("OCR_MODE", "local"),
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


@app.post("/api/photos/archive", tags=["Photos"])
def archive_photos_endpoint(
    body: dict,
    db: Session = Depends(get_db),
) -> dict:
    photo_ids: list = body.get("photo_ids", [])
    if not photo_ids:
        raise HTTPException(status_code=422, detail="photo_ids is required")
    from src.config import Api_Settings
    from pathlib import Path
    from src.models import PhotoQualityIssue
    settings = Api_Settings()
    root = Path(settings.DEFAULT_FOLDER) if hasattr(settings, "DEFAULT_FOLDER") else Path.home()
    zip_path = str(root / "MyPhotoArchive.zip")
    file_paths = []
    found_ids = []
    skipped_ids = []
    for pid in photo_ids:
        photo = get_photo_by_id(db, pid)
        if not photo:
            skipped_ids.append(pid)
            continue
        file_paths.append(photo.file_path)
        found_ids.append(pid)
    original_paths, _ = archive_photos_to_zip(file_paths, zip_path)
    # mark as archived in DB
    newly_archived_ids = []
    for pid in found_ids:
        photo = get_photo_by_id(db, pid)
        if photo and not photo.is_archived:
            photo.is_archived = True
            newly_archived_ids.append(pid)
    db.commit()
    if original_paths:
        create_history_action(
            db,
            action_type="archive_photos",
            photo_ids=found_ids,
            params={"zip_path": zip_path},
            undo_data={
                "zip_path": zip_path,
                "original_paths": original_paths,
                "newly_archived_ids": newly_archived_ids,
            },
        )
    return {
        "archived": len(original_paths),
        "skipped": len(skipped_ids),
        "zip_path": zip_path,
    }


@app.get("/api/photos/{photo_id}", tags=["Photos"], response_model=PhotoSchema)
def get_photo_endpoint(
    photo_id: int,
    db: Session = Depends(get_db),
) -> PhotoSchema:
    logger.info(f"Getting photo: {photo_id}")
    photo = get_photo_by_id(db, photo_id)
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    result = PhotoSchema.model_validate(photo)
    result.is_trash = get_photo_is_trash(db, photo_id)
    return result


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


@app.delete("/api/garbage/{photo_id}/issues", tags=["Garbage"])
def unmark_garbage_endpoint(photo_id: int, db: Session = Depends(get_db)) -> dict:
    from src.models import PhotoQualityIssue as QI
    deleted = db.query(QI).filter(QI.photo_id == photo_id).delete(synchronize_session=False)
    db.commit()
    return {"photo_id": photo_id, "removed": deleted > 0}


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


@app.post("/api/search/", tags=["Photos"], response_model=List[PhotoSearchResult])
async def search_photos_endpoint(
    request: QueryRequest,
    db: Session = Depends(get_db),
) -> List[PhotoSearchResult]:
    """Search photos by vector, returns results sorted by distance (most relevant first)."""
    logger.info(f"Received search request for text: {request.text_query}")
    pairs = await get_photos_by_vector(db, request.text_query, request.k)
    result = []
    for photo, distance in pairs:
        item = PhotoSearchResult(
            photo=PhotoSchema.model_validate(photo),
            distance=round(distance, 4),
        )
        item.photo.is_trash = get_photo_is_trash(db, photo.id)
        result.append(item)
    return result


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
    from uuid import uuid4
    thread_id = request.thread_id or str(uuid4())
    logger.info(f"Received chat message: {request.message} (thread_id: {thread_id})")

    inputs = {"messages": [HumanMessage(content=request.message)]}

    async def _invoke(tid: str):
        config = {"configurable": {"thread_id": tid}}
        return await agent_app.ainvoke(inputs, config), tid

    try:
        result, thread_id = await _invoke(thread_id)
    except Exception as exc:
        exc_str = str(exc).lower()
        # Corrupted checkpoint: assistant tool_calls with no following tool messages.
        # Heal automatically by starting a fresh thread.
        if "tool_call" in exc_str and "tool messages" in exc_str:
            fresh_id = str(uuid4())
            logger.warning(
                f"[chat] Corrupted checkpoint for thread {thread_id!r}, "
                f"retrying with fresh thread {fresh_id!r}: {exc}"
            )
            result, thread_id = await _invoke(fresh_id)
        elif "insufficient_quota" in exc_str or "rate_limit" in exc_str or "429" in exc_str:
            raise HTTPException(
                status_code=429,
                detail="AI API quota exceeded. Please check your billing / rate limits.",
            )
        elif "not_found" in exc_str or "404" in exc_str or "is not found" in exc_str:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Model not found: {exc}. "
                    "Check the model name on the Models page — "
                    "for Google Gemini use e.g. 'gemini-2.0-flash' or 'gemini-1.5-flash-latest'."
                ),
            )
        elif "401" in exc_str or "authentication" in exc_str or "invalid api key" in exc_str:
            raise HTTPException(
                status_code=502,
                detail="API key is invalid or missing. Please check your settings on the Models page.",
            )
        else:
            raise

    last_msg = result["messages"][-1]
    content = last_msg.content
    if isinstance(content, list):
        content = " ".join(
            block["text"] for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )

    return ChatResponse(
        response=content,
        thread_id=thread_id,
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
    from src.vector_db_services import get_embedding_dimension, current_vss_dimension, rebuild_embeddings_vss

    if config_type == "embedding":
        new_dim = get_embedding_dimension(request.model_name)
        cur_dim = current_vss_dimension(db)
        if new_dim != cur_dim:
            logger.info(f"[models] Embedding dimension changed {cur_dim}→{new_dim}, rebuilding VSS table")
            rebuild_embeddings_vss(db, new_dim)

    config = update_model_config(db, config_type, request)
    if not config:
        raise HTTPException(status_code=404, detail="Model config not found")

    # When switching to local, trigger eager loading immediately
    if request.mode == "local":
        import threading
        if config_type == "chat":
            from src.ai.registry import registry as _registry
            _registry.reset_model("chat")
            threading.Thread(target=_eager_load_chat_model, name="chat-warmup", daemon=True).start()
        elif config_type == "vision":
            from src.queues.vision_queue import warmup_vision_model
            warmup_vision_model()
        elif config_type == "ocr":
            from src.queues.ocr_queue import warmup_ocr_model
            warmup_ocr_model()
        elif config_type == "clip":
            from src.queues.clip_queue import warmup_clip_model
            warmup_clip_model()
        elif config_type == "translator":
            from src.queues.translation_queue import warmup_translation_model
            warmup_translation_model()
        elif config_type == "embedding":
            from src.queues.embedding_queue import warmup_embedding_model
            warmup_embedding_model()

    return config


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Prompts endpoints
# ---------------------------------------------------------------------------

@app.get("/api/prompts/", tags=["Prompts"], response_model=List[PromptResponse])
def get_prompts_endpoint(db: Session = Depends(get_db)):
    """Return all editable prompts sorted by key."""
    return get_all_prompts(db)


@app.put("/api/prompts/{key:path}", tags=["Prompts"], response_model=PromptResponse)
def update_prompt_endpoint(key: str, body: PromptUpdate, db: Session = Depends(get_db)):
    """Update the text of a prompt. Returns 404 if the key does not exist."""
    updated = update_prompt(db, key, body.text)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Prompt key {key!r} not found")
    return updated


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


# ---------------------------------------------------------------------------
# Template Tags endpoints
# ---------------------------------------------------------------------------

@app.get("/api/template-tags/", tags=["Template Tags"], response_model=PaginatedResponse[TemplateTagResponse])
def list_template_tags_endpoint(
    skip: int = Query(0), limit: int = Query(50), db: Session = Depends(get_db)
):
    tags, total = get_all_template_tags(db, skip=skip, limit=limit)
    return PaginatedResponse(items=tags, total=total, page=(skip // limit) + 1 if limit else 1, size=limit)


@app.post("/api/template-tags/", tags=["Template Tags"], response_model=TemplateTagResponse, status_code=201)
def create_template_tag_endpoint(body: TemplateTagCreate, db: Session = Depends(get_db)):
    from sqlalchemy.exc import IntegrityError
    try:
        tag = create_template_tag(db, name=body.name.strip(), clip_prompt=body.clip_prompt.strip())
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Template tag '{body.name}' already exists")
    from src.tasks.recompute_tasks import trigger_recompute_tags
    trigger_recompute_tags()
    return tag


@app.put("/api/template-tags/{tag_id}", tags=["Template Tags"], response_model=TemplateTagResponse)
def update_template_tag_endpoint(tag_id: int, body: TemplateTagUpdate, db: Session = Depends(get_db)):
    tag = update_template_tag(db, tag_id, name=body.name.strip(), clip_prompt=body.clip_prompt.strip())
    if not tag:
        raise HTTPException(status_code=404, detail="Template tag not found")
    from src.tasks.recompute_tasks import trigger_recompute_tags
    trigger_recompute_tags()
    return tag


@app.delete("/api/template-tags/{tag_id}", tags=["Template Tags"], status_code=204)
def delete_template_tag_endpoint(tag_id: int, db: Session = Depends(get_db)):
    if not delete_template_tag(db, tag_id):
        raise HTTPException(status_code=404, detail="Template tag not found")
    from src.tasks.recompute_tasks import trigger_recompute_tags
    trigger_recompute_tags()


# ---------------------------------------------------------------------------
# Template Categories endpoints
# ---------------------------------------------------------------------------

@app.get("/api/template-categories/", tags=["Template Categories"], response_model=PaginatedResponse[TemplateCategoryResponse])
def list_template_categories_endpoint(
    skip: int = Query(0), limit: int = Query(50), db: Session = Depends(get_db)
):
    cats, total = get_all_template_categories(db, skip=skip, limit=limit)
    return PaginatedResponse(items=cats, total=total, page=(skip // limit) + 1 if limit else 1, size=limit)


@app.post("/api/template-categories/", tags=["Template Categories"], response_model=TemplateCategoryResponse, status_code=201)
def create_template_category_endpoint(body: TemplateCategoryCreate, db: Session = Depends(get_db)):
    from sqlalchemy.exc import IntegrityError
    try:
        cat = create_template_category(db, name=body.name.strip(), clip_prompt=body.clip_prompt.strip())
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Template category '{body.name}' already exists")
    from src.tasks.recompute_tasks import trigger_recompute_categories
    trigger_recompute_categories()
    return cat


@app.put("/api/template-categories/{cat_id}", tags=["Template Categories"], response_model=TemplateCategoryResponse)
def update_template_category_endpoint(cat_id: int, body: TemplateCategoryUpdate, db: Session = Depends(get_db)):
    cat = update_template_category(db, cat_id, name=body.name.strip(), clip_prompt=body.clip_prompt.strip())
    if not cat:
        raise HTTPException(status_code=404, detail="Template category not found")
    from src.tasks.recompute_tasks import trigger_recompute_categories
    trigger_recompute_categories()
    return cat


@app.delete("/api/template-categories/{cat_id}", tags=["Template Categories"], status_code=204)
def delete_template_category_endpoint(cat_id: int, db: Session = Depends(get_db)):
    if not delete_template_category(db, cat_id):
        raise HTTPException(status_code=404, detail="Template category not found")
    from src.tasks.recompute_tasks import trigger_recompute_categories
    trigger_recompute_categories()


# ── Photo edit endpoints ───────────────────────────────────────────────────────

@app.put("/api/photos/{photo_id}", tags=["Photos"], response_model=PhotoSchema)
def update_photo_endpoint(photo_id: int, body: PhotoUpdate, db: Session = Depends(get_db)):
    photo = get_photo_by_id(db, photo_id)
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    old_description = photo.description
    updated = update_photo_fields(db, photo_id, **body.model_dump(exclude_none=True))
    db.commit()
    db.refresh(updated)
    if body.description is not None and body.description != old_description:
        from src.tasks.embedding_tasks import final_embedding_task
        final_embedding_task(photo_id, phase="edit")
    result = PhotoSchema.model_validate(updated)
    result.is_trash = get_photo_is_trash(db, photo_id)
    return result


@app.put("/api/photos/{photo_id}/flags", tags=["Photos"], response_model=PhotoSchema)
def update_photo_flags_endpoint(photo_id: int, body: PhotoFlagsUpdate, db: Session = Depends(get_db)):
    photo = get_photo_by_id(db, photo_id)
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    if body.is_doc is not None:
        set_photo_is_doc(db, photo_id, body.is_doc)
    if body.is_trash is not None:
        if body.is_trash:
            mark_photo_as_trash(db, photo_id)
        else:
            unmark_photo_as_trash(db, photo_id)
    db.commit()
    db.refresh(photo)
    result = PhotoSchema.model_validate(photo)
    result.is_trash = get_photo_is_trash(db, photo_id)
    return result


@app.post("/api/photos/{photo_id}/tags", tags=["Photos"], status_code=201, response_model=PhotoTagResponse)
def link_photo_tag_endpoint(photo_id: int, body: PhotoTagLink, db: Session = Depends(get_db)):
    if not get_photo_by_id(db, photo_id):
        raise HTTPException(status_code=404, detail="Photo not found")
    pt = link_photo_tag(db, photo_id, body.name)
    db.commit()
    db.refresh(pt)
    return PhotoTagResponse(id=pt.tag_id, name=pt.tag.name, confidence_score=pt.confidence_score)


@app.delete("/api/photos/{photo_id}/tags/{tag_id}", tags=["Photos"], status_code=204)
def unlink_photo_tag_endpoint(photo_id: int, tag_id: int, db: Session = Depends(get_db)):
    if not unlink_photo_tag(db, photo_id, tag_id):
        raise HTTPException(status_code=404, detail="Tag not linked to this photo")
    db.commit()


@app.post("/api/photos/{photo_id}/categories", tags=["Photos"], status_code=201, response_model=PhotoCategoryResponse)
def link_photo_category_endpoint(photo_id: int, body: PhotoCategoryLink, db: Session = Depends(get_db)):
    if not get_photo_by_id(db, photo_id):
        raise HTTPException(status_code=404, detail="Photo not found")
    pc = link_photo_category(db, photo_id, body.name)
    db.commit()
    db.refresh(pc)
    return PhotoCategoryResponse(id=pc.category_id, name=pc.category.name, confidence_score=pc.confidence_score)


@app.delete("/api/photos/{photo_id}/categories/{cat_id}", tags=["Photos"], status_code=204)
def unlink_photo_category_endpoint(photo_id: int, cat_id: int, db: Session = Depends(get_db)):
    if not unlink_photo_category(db, photo_id, cat_id):
        raise HTTPException(status_code=404, detail="Category not linked to this photo")
    db.commit()


@app.post("/api/photos/{photo_id}/reindex", tags=["Photos"])
async def reindex_photo_endpoint(
    photo_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Re-save a photo's description into the vector search index using existing metadata."""
    photo = get_photo_by_id(db, photo_id)
    if not photo:
        raise HTTPException(status_code=404, detail=f"Photo {photo_id} not found")
    background_tasks.add_task(final_embedding_task, photo_id)
    return {"status": "queued", "photo_id": photo_id}


@app.post("/api/photos/{photo_id}/run-pipeline", tags=["Photos"])
async def run_pipeline_for_photo_endpoint(
    photo_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Clear tags/categories and re-run the full pipeline for a single photo."""
    from src.models import PhotoTag, PhotoCategory
    photo = get_photo_by_id(db, photo_id)
    if not photo:
        raise HTTPException(status_code=404, detail=f"Photo {photo_id} not found")
    db.query(PhotoTag).filter_by(photo_id=photo_id).delete()
    db.query(PhotoCategory).filter_by(photo_id=photo_id).delete()
    db.commit()

    def _run():
        import asyncio
        from src.incoming_pipeline import run_pipelines_batch
        asyncio.run(run_pipelines_batch([photo_id]))

    import threading
    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return {"status": "queued", "photo_id": photo_id}


# ---------------------------------------------------------------------------
# Processing Page endpoints
# ---------------------------------------------------------------------------

@app.get("/api/pipeline/active", tags=["Pipeline"], response_model=List[PipelineTaskSchema])
def get_active_pipeline_tasks_endpoint(db: Session = Depends(get_db)):
    """Return all currently pending or running pipeline tasks (for the Processing Page)."""
    from src.pipeline_tracker import get_active_pipeline_tasks
    return get_active_pipeline_tasks(db)


@app.get("/api/pipeline/recent", tags=["Pipeline"], response_model=List[PipelineTaskSchema])
def get_recent_pipeline_tasks_endpoint(
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Return the most recently created pipeline tasks."""
    from src.pipeline_tracker import get_recent_pipeline_tasks
    return get_recent_pipeline_tasks(db, limit=limit)


@app.get("/api/photos/{photo_id}/pipeline", tags=["Pipeline"], response_model=List[PipelineTaskSchema])
def get_photo_pipeline_tasks_endpoint(photo_id: int, db: Session = Depends(get_db)):
    """Return all pipeline tasks for a specific photo."""
    from src.pipeline_tracker import get_photo_pipeline_tasks
    return get_photo_pipeline_tasks(db, photo_id)
