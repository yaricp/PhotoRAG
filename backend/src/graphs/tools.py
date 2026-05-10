from loguru import logger
from typing import List, Optional
from pathlib import Path
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.db_service import (
    get_photos_by_vector, get_all_photos, get_photo_by_id,
    get_all_categories, get_all_tags, get_all_cameras,
    get_all_geopositions, get_photos_by_category_id,
    get_history_actions, perform_undo,
    get_setting, create_history_action,
)
from src.database import SessionLocal
from src.ai.registry import registry
from src.utils import extract_exif, resize_image
from src.schemas import Photo


class SearchMetadataArgs(BaseModel):
    category_ids: Optional[List[int]] = Field(None, description="Filter by category ID")
    tag_ids: Optional[List[int]] = Field(None, description="Filter by tag ID")
    geoposition_id: Optional[int] = Field(None, description="Filter by geoposition ID")
    camera_id: Optional[int] = Field(None, description="Filter by camera ID")
    is_doc: Optional[bool] = Field(None, description="Filter for document photos only")
    limit: int = Field(10, description="Maximum number of photos to return")


def _serialize_photos(photos: list) -> str:
    """Serialize a list of ORM Photo objects to a JSON string."""
    result = [Photo.model_validate(p).model_dump_json() for p in photos]
    return "[" + ",".join(result) + "]"


@tool
def search_photos_semantic(query: str, k: int = 5) -> str:
    """
    Search for photos using natural language descriptions (semantic search).

    Use this tool when:
    - The user describes a scene, object, or memory in free form
    - The user does NOT specify exact filters like ID, category, or tag
    - The query is vague or human-like (e.g., "photos of money", "a dog in the park")

    Do NOT use this tool when:
    - The user provides a specific photo ID → use get_photo_details
    - The user asks for filtering by structured fields (category, tag, camera) → use search_photos_metadata

    Input:
    - query: natural language description of the photo(s)
    - k: number of results to return (default 5)

    Examples:
    - "Find photos of money"
    - "Show me pictures of documents"
    - "Photos with food on the table"

    Returns:
    A JSON string with a list of Photo objects.
    """
    logger.info(f"[tool] semantic search: {query}")
    db = SessionLocal()
    try:
        photos = get_photos_by_vector(db, query, k)
        if not photos:
            return "No photos found matching that description."
        return _serialize_photos(photos)
    finally:
        db.close()


@tool
def search_photos_by_category_id(category_id: int) -> str:
    """
    Search for photos by category id.

    Use this tool when:
    - The user asks to filter photos by category id

    Returns:
    A JSON string with a list of Photo objects.
    """
    logger.info(f"[tool] category search: {category_id}")
    db = SessionLocal()
    try:
        photos = get_photos_by_category_id(db, category_id)
        if not photos:
            return "No photos found in this category."
        return _serialize_photos(photos)
    finally:
        db.close()


@tool
def search_photos_metadata(
    category_ids: Optional[List[int]] = None,
    tag_ids: Optional[List[int]] = None,
    geoposition_id: Optional[int] = None,
    camera_id: Optional[int] = None,
    is_doc: Optional[bool] = None,
    limit: int = 10
) -> str:
    """
    Search for photos using structured metadata filters.

    Use this tool when:
    - The user specifies filters like category, tag, camera, or document type
    - The request is structured rather than descriptive

    Do NOT use this tool when:
    - The user describes a scene in natural language → use search_photos_semantic
    - The user asks about a specific photo ID → use get_photo_details

    Input:
    - category_ids: filter by category. Can be a list of category IDs.
    - tag_ids: filter by tag. Can be a list of tag IDs.
    - camera_id: filter by camera.
    - geoposition_id: filter by geoposition.
    - is_doc: filter document-type photos (True/False)
    - limit: maximum number of results

    Examples:
    - "Find document photos"
    - "Show photos taken with camera 2"
    - "Photos with tag 5"

    Returns:
    A JSON string with a list of Photo objects.
    """
    logger.info(f"[tool] metadata search: {category_ids}, {tag_ids}, {geoposition_id}, {camera_id}, {is_doc}, {limit}")
    db = SessionLocal()
    try:
        photos, total = get_all_photos(
            db,
            category_ids=category_ids,
            tag_ids=tag_ids,
            geoposition_id=geoposition_id,
            camera_id=camera_id,
            is_doc=is_doc,
            limit=limit
        )
        if not photos:
            return "No photos found matching these criteria."
        return _serialize_photos(photos)
    finally:
        db.close()


@tool
def get_photo_details(photo_id: int) -> str:
    """
    Get full details for a specific photo by its ID.

    MUST be used when:
    - The user mentions a specific photo ID (e.g., "photo 20", "ID 15")
    - The user asks for details, tags, description, or metadata of a specific photo
    - The user refers to "this photo" after selecting or referencing an ID

    Do NOT use any other tool if a photo ID is provided — always use this tool.

    Input:
    - photo_id: unique identifier of the photo

    Examples:
    - "Tell me about photo 20"
    - "What is in photo with ID 15?"
    - "Show tags and description for photo 7"

    Returns:
    A JSON string with a list containing one Photo object.
    """
    logger.info(f"[tool] photo details: {photo_id}")
    db = SessionLocal()
    try:
        p = get_photo_by_id(db, photo_id)
        if not p:
            return f"Photo with ID {photo_id} not found."
        photo_schema = Photo.model_validate(p)
        return "[" + photo_schema.model_dump_json() + "]"
    finally:
        db.close()


@tool
def get_categories() -> str:
    """
    Get all categories.
    Results format:
    ID: {category.id} | Name: {category.name}
    """
    logger.info("[tool] categories")
    db = SessionLocal()
    try:
        result = "Available Categories:\n"
        for category in get_all_categories(db):
            result += f"ID: {category.id} | Name: {category.name}\n"
        logger.info(f"[tool] categories result: {result}")
        return result
    finally:
        db.close()


@tool
def get_tags() -> str:
    """
    Get all tags.
    Results format:
    ID: {tag.id} | Name: {tag.name}
    """
    db = SessionLocal()
    try:
        result = "Available Tags:\n"
        for tag in get_all_tags(db):
            result += f"ID: {tag.id} | Name: {tag.name}\n"
        logger.info(f"[tool] tags result: {result}")
        return result
    finally:
        db.close()


@tool
def get_cameras() -> str:
    """
    Get all cameras.
    Results format:
    ID: {camera.id} | Make: {camera.make} |
    Model: {camera.model} | Serial Number: {camera.serial_number}
    """
    logger.info("[tool] cameras")
    db = SessionLocal()
    try:
        result = "Available Cameras:\n"
        for camera in get_all_cameras(db):
            result += f"ID: {camera.id} | Make: {camera.make} |"
            result += f" Model: {camera.model} |"
            result += f" Serial Number: {camera.serial_number}\n"
        logger.info(f"[tool] cameras result: {result}")
        return result
    finally:
        db.close()


@tool
def get_geopositions() -> str:
    """
    Get all geopositions.
    Results format:
    ID: {geoposition.id} | Address: {geoposition.address} |
    Latitude: {geoposition.latitude} | Longitude: {geoposition.longitude}
    """
    logger.info("[tool] geoposition")
    db = SessionLocal()
    try:
        result = "Available Geopositions:\n"
        for geoposition in get_all_geopositions(db):
            result += f"ID: {geoposition.id} | "
            result += f"Address: {geoposition.address}\n"
            result += f"Latitude: {geoposition.latitude} | "
            result += f"Longitude: {geoposition.longitude}\n"
        logger.info(f"[tool] geoposition result: {result}")
        return result
    finally:
        db.close()


@tool
def resize_photo(photo_id: int, width: int, height: int) -> str:
    """
    Resize a photo to the specified width and height.

    Use this tool when:
    - The user wants to resize a photo
    - The user provides photo ID, width, and height

    Input:
    - photo_id: unique identifier of the photo
    - width: new width in pixels
    - height: new height in pixels

    Returns:
    Status message with the new dimensions.
    """
    logger.info(f"[tool] resize photo: {photo_id} {width}x{height}")
    db = SessionLocal()
    try:
        p = get_photo_by_id(db, photo_id)
        if not p:
            return f"Photo with ID {photo_id} not found."
        new_path = resize_image(p.file_path, width, height)
        return f"Photo resized successfully. New path: {new_path}"
    finally:
        db.close()


@tool
def get_exif_data(photo_id: int) -> str:
    """
    Get EXIF data for a photo.

    Use this tool when:
    - The user wants to get EXIF data for a photo
    - The user provides photo ID

    Input:
    - photo_id: unique identifier of the photo

    Returns:
    Status message with the EXIF data.
    """
    logger.info(f"[tool] exif data: {photo_id}")
    db = SessionLocal()
    try:
        p = get_photo_by_id(db, photo_id)
        if not p:
            return f"Photo with ID {photo_id} not found."
        exif_data = extract_exif(p.file_path)
        logger.info(f"[tool] exif data result: {exif_data}")
        return f"EXIF data for photo {photo_id}: {exif_data}"
    finally:
        db.close()


def _get_allowed_root(db) -> Path:
    val = get_setting(db, "default_folder")
    root = Path(val) if val else Path.home()
    return root.resolve()


def _safe_resolve(root: Path, relative: str) -> Path:
    target = (root / relative).resolve()
    if not str(target).startswith(str(root)):
        raise ValueError(f"Path escapes allowed root: {target}")
    return target


@tool
def create_folder(folder_name: str, parent_path: str = "") -> str:
    """
    Create a new folder inside the allowed root directory.

    The allowed root is the DEFAULT_FOLDER setting if set, otherwise the user's home directory.
    The folder_name must not contain path separators.
    The parent_path is relative to the allowed root (empty = root itself).

    Returns a success message with the full path created, or an error if the path
    would escape the allowed root or the folder already exists.
    """
    import os
    logger.info(f"[tool] create_folder: {folder_name!r} in {parent_path!r}")
    if os.sep in folder_name or "/" in folder_name:
        return "Error: folder_name must not contain path separators."
    db = SessionLocal()
    try:
        root = _get_allowed_root(db)
        try:
            relative = str(Path(parent_path) / folder_name) if parent_path else folder_name
            target = _safe_resolve(root, relative)
        except ValueError as e:
            return f"Error: {e}"
        if target.exists():
            return f"Error: folder already exists: {target}"
        target.mkdir(parents=True, exist_ok=False)
        create_history_action(
            db,
            action_type="create_folder",
            photo_ids=None,
            params={"path": str(target)},
            undo_data={"path": str(target)},
        )
        return f"Folder created: {target}"
    finally:
        db.close()


@tool
def move_photos(photo_ids: List[int], destination_folder: str) -> str:
    """
    Move photos (by ID) to a destination folder within the allowed root.

    destination_folder is relative to the allowed root.
    DB file_path is updated for each moved photo.
    Original paths are saved in history for rollback.

    Returns a summary of moved files or an error.
    """
    import shutil
    logger.info(f"[tool] move_photos: {photo_ids} → {destination_folder!r}")
    db = SessionLocal()
    try:
        root = _get_allowed_root(db)
        try:
            dest = _safe_resolve(root, destination_folder)
        except ValueError as e:
            return f"Error: {e}"
        dest.mkdir(parents=True, exist_ok=True)
        original_paths: dict = {}
        moved = []
        skipped = []
        for pid in photo_ids:
            photo = get_photo_by_id(db, pid)
            if not photo:
                skipped.append(f"ID {pid} not found")
                continue
            if not Path(photo.file_path).exists():
                skipped.append(f"ID {pid} file missing: {photo.file_path}")
                continue
            original_paths[str(pid)] = photo.file_path
            filename = Path(photo.file_path).name
            new_path = str(dest / filename)
            shutil.move(photo.file_path, new_path)
            photo.file_path = new_path
            moved.append(filename)
        db.commit()
        if original_paths:
            create_history_action(
                db,
                action_type="move_photos",
                photo_ids=list(photo_ids),
                params={"destination": str(dest)},
                undo_data={"original_paths": original_paths},
            )
        parts = [f"Moved {len(moved)} photo(s) to {dest}."]
        if skipped:
            parts.append("Skipped: " + "; ".join(skipped))
        return " ".join(parts)
    finally:
        db.close()


@tool
def archive_photos(photo_ids: List[int]) -> str:
    """
    Zip the specified photos into MyPhotoArchive.zip inside the allowed root
    and mark each photo as archived in the database.

    - Allowed root = DEFAULT_FOLDER setting, or user home directory if not set.
    - If MyPhotoArchive.zip already exists, new files are appended (not overwritten).
    - Only photos not yet marked is_archived=True are newly archived.
    - Saves a history action for precise undo.

    Returns: path to the zip and count of photos added.
    """
    import zipfile
    logger.info(f"[tool] archive_photos: {photo_ids}")
    db = SessionLocal()
    try:
        root = _get_allowed_root(db)
        zip_path = root / "MyPhotoArchive.zip"
        added_names: list = []
        newly_archived_ids: list = []
        skipped = []
        with zipfile.ZipFile(zip_path, "a") as zf:
            for pid in photo_ids:
                photo = get_photo_by_id(db, pid)
                if not photo:
                    skipped.append(f"ID {pid} not found")
                    continue
                if not Path(photo.file_path).exists():
                    skipped.append(f"ID {pid} file missing")
                    continue
                arcname = Path(photo.file_path).name
                zf.write(photo.file_path, arcname)
                added_names.append(arcname)
                if not photo.is_archived:
                    photo.is_archived = True
                    newly_archived_ids.append(pid)
        db.commit()
        if added_names:
            create_history_action(
                db,
                action_type="archive_photos",
                photo_ids=list(photo_ids),
                params={"zip_path": str(zip_path)},
                undo_data={
                    "zip_path": str(zip_path),
                    "added_names": added_names,
                    "newly_archived_ids": newly_archived_ids,
                },
            )
        parts = [f"Archived {len(added_names)} photo(s) into {zip_path}."]
        if skipped:
            parts.append("Skipped: " + "; ".join(skipped))
        return " ".join(parts)
    finally:
        db.close()


@tool
def get_action_history() -> str:
    """
    Return the last 20 recorded actions (create_folder, move_photos, archive_photos).

    Use this when:
    - The user asks "what did you do?", "show history", "what actions were taken?"

    Returns a human-readable summary of recent actions with their IDs and timestamps.
    """
    import json
    logger.info("[tool] get_action_history")
    db = SessionLocal()
    try:
        actions = get_history_actions(db, limit=20)
        if not actions:
            return "No actions recorded yet."
        lines = []
        for a in actions:
            params = json.loads(a.params)
            ts = a.created_at.strftime("%Y-%m-%d %H:%M:%S") if a.created_at else "unknown"
            lines.append(f"[{a.id}] {ts} — {a.action_type}: {params}")
        return "\n".join(lines)
    finally:
        db.close()


@tool
def undo_last_action() -> str:
    """
    Undo the most recent recorded action.

    - create_folder  → removes the created directory (only if empty)
    - move_photos    → moves files back to original locations, restores DB paths
    - archive_photos → deletes or trims the created zip file, un-archives photos

    Use when:
    - The user says "undo", "undo that", "revert last action", "go back"

    Returns a confirmation of what was undone, or an error if nothing to undo.
    """
    logger.info("[tool] undo_last_action")
    db = SessionLocal()
    try:
        return perform_undo(db)
    finally:
        db.close()


@tool
def describe_photo(photo_id: int) -> str:
    """
    Get description for a photo.

    Use this tool when:
    - The user wants to get description for a photo
    - The user provides photo ID

    Input:
    - photo_id: unique identifier of the photo

    Returns:
    Status message with the description.
    """
    logger.info(f"[tool] description: {photo_id}")
    db = SessionLocal()
    try:
        p = get_photo_by_id(db, photo_id)
        if not p:
            return f"Photo with ID {photo_id} not found."
        desc = registry.generate_vision_text(
            file_path=p.file_path,
            prompt_key="describe_scene",
        )
        logger.info(f"[tool] description result: {desc}")
        return f"Description for photo {photo_id}: {desc}"
    finally:
        db.close()
