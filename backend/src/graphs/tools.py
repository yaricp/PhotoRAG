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
    get_quality_summary, get_garbage_photos_with_issues, get_garbage_photo_paths,
    get_photos_by_tag_id as _get_photos_by_tag_id,
    search_photos_by_exif_params,
    get_or_create_tag, add_photo_tag_with_score,
    get_or_create_category, add_photo_category_with_score,
    update_photo_geoposition, get_or_create_photo_hash,
)
from src.database import SessionLocal
from src.ai.registry import registry
from src.utils import extract_exif, resize_image, archive_photos_to_zip
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
    Search for photos using a natural-language description (semantic / AI search).

    Use when the user describes a scene, subject, or feeling in plain words.
    Do NOT use when the user gives a specific photo ID (→ get_photo_details)
    or explicit structured filters (→ search_photos_metadata or filter_photos).

    User query examples:
    - "Find photos of money"
    - "Show me pictures from the beach"
    - "Photos with food on the table"
    - "Pictures that look like a party"
    - "Find shots of mountains or nature"
    - "Найди фотографии с едой"
    - "Покажи снимки с природой"
    - "Фото где есть люди"

    Returns: JSON list of Photo objects.
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
    Return all photos that belong to a specific category (by numeric ID).

    Use get_categories first if you need to look up an ID from a name.

    User query examples:
    - "Show all photos in category 3"
    - "Find photos from the Travel category"   ← first call get_categories
    - "List pictures categorised as Nature"
    - "Give me all Family photos"
    - "Покажи все фото из категории 'Природа'"
    - "Фотографии категории 5"

    Returns: JSON list of Photo objects.
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
    Search for photos using structured metadata filters (category, tag, camera, location).

    Prefer filter_photos when date filters (year/month/day) are also needed.
    Do NOT use when the user describes a scene in words → search_photos_semantic.
    Do NOT use when the user provides a photo ID → get_photo_details.

    User query examples:
    - "Find document photos"
    - "Show scanned documents"
    - "Photos taken with camera 2"
    - "Pictures tagged with label 5"
    - "Photos from location 3"
    - "Show photos that are documents or receipts"
    - "Найди фотографии сделанные камерой 1"
    - "Покажи фото с тегом 4"

    Returns: JSON list of Photo objects.
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
    Get full details for a specific photo by its ID (tags, description, EXIF, location…).

    MUST be used whenever the user references a specific photo by number or ID.
    Do NOT use any other search tool when an ID is already known.

    User query examples:
    - "Tell me about photo 20"
    - "What is in photo number 15?"
    - "Show me the details for picture 7"
    - "Info on photo with position 4"
    - "What tags does photo 9 have?"
    - "Describe the selected photo" (when the user selected one photo)
    - "Расскажи про фото номер 12"
    - "Что на фотографии 8?"
    - "Покажи информацию о снимке 3"

    Returns: JSON list containing one Photo object.
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
    Return a list of all photo categories with their IDs.

    Call this first whenever the user mentions a category by name,
    so you can look up the correct ID before calling other tools.

    User query examples:
    - "What categories are there?"
    - "Show me all the albums"
    - "What groups are my photos organised into?"
    - "List all photo types"
    - "Какие категории есть?"
    - "Покажи все альбомы"
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
    Return a list of all photo tags (labels) with their IDs.

    Call this first whenever the user mentions a tag by name,
    so you can look up the correct ID before calling other tools.

    User query examples:
    - "What tags are available?"
    - "Show all labels"
    - "What keywords exist in my library?"
    - "List all photo labels"
    - "Какие теги есть?"
    - "Покажи все метки"
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
    Return a list of all cameras (make, model, serial) with their IDs.

    Call this first whenever the user asks about photos from a specific camera or device,
    so you can look up the correct camera_id before calling other tools.

    User query examples:
    - "What cameras do I have?"
    - "Which devices took my photos?"
    - "Show all cameras in my library"
    - "What phones or cameras have I used?"
    - "Какие камеры есть в моей библиотеке?"
    - "Покажи список устройств"
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
    Return a list of all known locations (address, latitude, longitude) with their IDs.

    Call this first whenever the user asks about photos from a specific place,
    so you can look up the correct geoposition_id before calling other tools.

    User query examples:
    - "What locations are in my library?"
    - "Show all the places my photos were taken"
    - "Which cities do I have photos from?"
    - "List all saved places"
    - "Какие места есть в моей библиотеке?"
    - "Покажи все локации"
    - "Из каких городов у меня есть фото?"
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
    Resize a photo file to a new width and height (overwrites the original file on disk).

    ⚠️ BEFORE CALLING THIS TOOL — ASK USER PERMISSION:
    Tell the user: "I am going to resize photo [photo_id] to [width]×[height] pixels.
    The original file will be overwritten on disk."
    Then ask: "Should I go ahead?"
    Only call this tool after the user confirms (yes / ok / go ahead / да / давай).

    User query examples:
    - "Make photo 3 smaller — 800 by 600"
    - "Resize picture number 10"
    - "Scale down photo 20 to 1024 pixels wide"
    - "I need photo 5 at half size"
    - "Уменьши фото 7 до 800 на 600"
    - "Измени размер снимка номер 4"
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
    Return raw EXIF metadata for a photo (camera settings, GPS, timestamps, etc.).

    Read-only — no changes are made.

    User query examples:
    - "Show EXIF data for photo 5"
    - "What camera settings were used for picture 3?"
    - "Was photo 8 taken with flash?"
    - "What focal length was used for photo 12?"
    - "Show me the technical details of photo 6"
    - "Покажи EXIF данные фото 7"
    - "Какие настройки камеры у снимка 4?"
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
    Create a new folder on disk inside the allowed photos root directory.

    ⚠️ BEFORE CALLING THIS TOOL — ASK USER PERMISSION:
    Tell the user exactly what will be created, for example:
    "I am going to create a new folder called '[folder_name]' inside [parent_path or 'your photos folder']."
    Then ask: "Should I go ahead?"
    Only call this tool after the user confirms (yes / ok / go ahead / да / давай).

    The folder_name must not contain path separators (/ or \\).
    parent_path is relative to the allowed root (leave empty to create at the root level).
    Saves a history action — can be undone with undo_last_action.

    User query examples:
    - "Make a folder called Vacation"
    - "Create a new album named Beach 2024"
    - "I need a place to put my family photos — make a folder"
    - "Add a folder named Events inside the 2024 folder"
    - "Создай папку 'Отпуск'"
    - "Мне нужна новая папка для праздничных снимков"
    - "Сделай альбом 'Семья' внутри папки 2024"
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
    Move photos to a different folder on disk and update their paths in the database.

    ⚠️ BEFORE CALLING THIS TOOL — ASK USER PERMISSION:
    Tell the user: "I am going to move [N] photo(s) (IDs: [photo_ids]) to the folder
    '[destination_folder]'. The files will be physically moved on disk and the
    database will be updated."
    Then ask: "Should I go ahead?"
    Only call this tool after the user confirms (yes / ok / go ahead / да / давай).

    destination_folder is relative to the allowed photos root.
    The destination is created automatically if it does not exist.
    Saves a history action — can be undone with undo_last_action.

    User query examples:
    - "Move photo 5 to the Vacation folder"
    - "Put pictures 3, 7 and 9 into the Events album"
    - "Sort photo number 12 into the Family folder"
    - "Send the selected photos to the archive folder"
    - "Перемести фото 4 в папку 'Природа'"
    - "Положи снимки 1 и 2 в папку 'Семья'"
    - "Перенеси эти фотографии в альбом Отпуск"
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
    Pack selected photos into MyPhotoArchive.zip and mark them as archived in the database.

    ⚠️ BEFORE CALLING THIS TOOL — ASK USER PERMISSION:
    Tell the user: "I am going to add [N] photo(s) (IDs: [photo_ids]) to
    MyPhotoArchive.zip and mark them as archived. The files remain on disk but will
    be flagged as archived in the app."
    Then ask: "Should I go ahead?"
    Only call this tool after the user confirms (yes / ok / go ahead / да / давай).

    If MyPhotoArchive.zip already exists, new files are appended (not overwritten).
    Saves a history action — can be undone with undo_last_action.

    User query examples:
    - "Archive these photos"
    - "Pack photos 3, 5 and 8 into the archive"
    - "Zip up the old family pictures"
    - "I want to archive the duplicate shots"
    - "Put photo 10 in the archive"
    - "Добавь эти фотографии в архив"
    - "Заархивируй снимки 2 и 7"
    """
    logger.info(f"[tool] archive_photos: {photo_ids}")
    db = SessionLocal()
    try:
        root = _get_allowed_root(db)
        zip_path = root / "MyPhotoArchive.zip"
        file_paths = []
        found_ids = []
        skipped = []
        for pid in photo_ids:
            photo = get_photo_by_id(db, pid)
            if not photo:
                skipped.append(f"ID {pid} not found")
                continue
            file_paths.append(photo.file_path)
            found_ids.append(pid)
        added_names, missing = archive_photos_to_zip(file_paths, str(zip_path))
        for fp in missing:
            skipped.append(f"missing: {fp}")
        newly_archived_ids = []
        for pid in found_ids:
            photo = get_photo_by_id(db, pid)
            if photo and not photo.is_archived:
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
                    "original_paths": added_names,  # dict: arcname → original_file_path
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
    Return the last 20 recorded actions (folder creation, moves, archives, annotations…).

    Also call this BEFORE calling undo_last_action so you can tell the user
    what exactly will be undone.

    User query examples:
    - "What did you do?"
    - "Show me the history"
    - "What actions were taken?"
    - "What was the last thing you changed?"
    - "Show recent operations"
    - "Что ты сделал?"
    - "Покажи историю действий"
    - "Что последнее было изменено?"
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
    Undo the most recently recorded action (folder, move, archive, tag, category, geoposition).

    ⚠️ BEFORE CALLING THIS TOOL — ASK USER PERMISSION:
    First call get_action_history to find out what the last action was.
    Tell the user: "The last action was [action_type] from [timestamp]. I will reverse it."
    Then ask: "Should I undo this?"
    Only call this tool after the user confirms (yes / ok / undo it / да / отмени).

    What each undo does:
    - create_folder  → removes the folder (only if empty)
    - move_photos    → moves files back to their original locations, restores DB paths
    - archive_photos → removes files from the zip, un-marks photos as archived
    - add_tag        → removes the tag from the affected photos
    - add_category   → removes the category from the affected photos
    - add_geoposition → restores the previous geoposition for the affected photos

    User query examples:
    - "Undo that"
    - "Go back"
    - "Revert what you just did"
    - "I changed my mind — cancel the last step"
    - "That was a mistake, undo it"
    - "Отмени последнее действие"
    - "Верни как было"
    - "Я передумал, отмени"
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
    Generate an AI visual description of a photo using the vision model.
    ⏳ Slow — runs a large vision model. Use only when the user explicitly asks
    for a description or asks "what is in this photo?".

    Read-only — no changes are made to the photo.

    User query examples:
    - "What is in photo 5?"
    - "Describe picture number 8"
    - "Tell me what you see in photo 12"
    - "What does photo 3 look like?"
    - "Explain what's happening in picture 7"
    - "Что изображено на фото 6?"
    - "Опиши снимок номер 10"
    - "Что на этой фотографии?"
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


# =============================================================================
# Group A — Garbage / Quality
# =============================================================================

@tool
def get_garbage_photos(issue_type: str = "", limit: int = 20) -> str:
    """
    Show photos that have been detected as potential garbage (low quality).

    Read-only — no changes are made.

    If issue_type is empty: return a count summary grouped by issue type,
    plus a sample of flagged photos (up to limit).
    If issue_type is given: return photos flagged with that specific issue.

    Known issue_type values: blur, brightness, resolution, exif, entropy,
    edge_density, screenshot.

    User query examples:
    - "Show me the bad photos"
    - "Which pictures are blurry?"
    - "Find photos that are too dark"
    - "Show garbage photos"
    - "What photos should I delete?"
    - "Покажи плохие фотографии"
    - "Какие снимки размытые?"
    - "Найди тёмные фотографии"
    """
    logger.info(f"[tool] get_garbage_photos: issue_type={issue_type!r} limit={limit}")
    db = SessionLocal()
    try:
        summary = get_quality_summary(db)
        photos, total = get_garbage_photos_with_issues(db, issue_type=issue_type, limit=limit)
        if not photos:
            return f"Quality issue summary: {summary}. No flagged photos found."
        return _serialize_photos(photos)
    finally:
        db.close()


@tool
def get_garbage_total_size(issue_type: str = "") -> str:
    """
    Calculate the total file size occupied by potential garbage photos.

    Read-only — no files are deleted or changed.

    If issue_type is given: count only photos with that specific quality issue.
    If empty: count all photos that have any quality issue.

    User query examples:
    - "How much space do the bad photos take?"
    - "How many gigabytes of garbage photos do I have?"
    - "How much disk space could I save by deleting bad photos?"
    - "Сколько места занимают плохие фото?"
    - "Какой объём занимают размытые снимки?"
    """
    import os
    logger.info(f"[tool] get_garbage_total_size: issue_type={issue_type!r}")
    db = SessionLocal()
    try:
        paths = get_garbage_photo_paths(db, issue_type=issue_type)
        total_bytes = 0
        missing = 0
        for p in paths:
            try:
                total_bytes += os.stat(p).st_size
            except OSError:
                missing += 1
        mb = total_bytes / (1024 * 1024)
        gb = mb / 1024
        label = issue_type or "all quality issues"
        size_str = f"{gb:.2f} GB ({mb:.1f} MB)" if gb >= 1 else f"{mb:.1f} MB"
        result = f"Garbage photos ({label}): {len(paths)} file(s), total size {size_str}."
        if missing:
            result += f" ({missing} file(s) missing on disk, excluded from total.)"
        return result
    finally:
        db.close()


@tool
def estimate_photo_quality_quick(photo_id: int) -> str:
    """
    Run a fast, lightweight quality check on a single photo using pixel-level analysis.
    No AI model is loaded — results are available in under a second.

    Returns all quality metrics and a garbage verdict:
    - brightness (mean luminance; <30 = too dark, >220 = overexposed)
    - blur_variance (Laplacian; <100 = blurry)
    - edge_density (fraction of edge pixels; <0.02 = featureless)
    - entropy (texture complexity; <3.0 = flat/repetitive)
    - is_screenshot, is_thumbnail, exif_missing
    - overall_verdict: "likely garbage" / "acceptable" / "good"

    Read-only — no changes are made.

    User query examples:
    - "Is photo 5 any good?"
    - "Check if picture number 12 is blurry"
    - "Is photo 8 worth keeping?"
    - "Quickly analyse the quality of photo 20"
    - "Проверь качество фото номер 3"
    - "Стоит ли хранить фото 7?"
    """
    from src.quality_checks import (
        check_resolution, check_exif, check_brightness,
        check_edge_density, check_blur, check_entropy, check_screenshot,
    )
    from src.metadata import get_exif_data as _get_exif
    logger.info(f"[tool] estimate_photo_quality_quick: {photo_id}")
    db = SessionLocal()
    try:
        photo = get_photo_by_id(db, photo_id)
        if not photo:
            return f"Photo {photo_id} not found."
        fp = photo.file_path
        exif_raw = _get_exif(fp)
        is_thumb, pixels = check_resolution(fp)
        exif_bad, _ = check_exif(exif_raw)
        bright_bad, brightness = check_brightness(fp)
        edge_bad, edge_density = check_edge_density(fp)
        blur_bad, blur_var = check_blur(fp)
        entropy_bad, entropy = check_entropy(fp)
        screenshot_bad, screenshot_score = check_screenshot(fp)
        issues = []
        if is_thumb:
            issues.append("thumbnail/tiny resolution")
        if exif_bad:
            issues.append("no camera EXIF")
        if bright_bad:
            issues.append("bad brightness")
        if edge_bad:
            issues.append("featureless/flat")
        if blur_bad:
            issues.append("blurry")
        if entropy_bad:
            issues.append("low entropy")
        if screenshot_bad:
            issues.append("screenshot-like")
        verdict = "likely garbage" if len(issues) >= 2 else ("acceptable" if issues else "good")
        return (
            f"Photo {photo_id} quality check:\n"
            f"  brightness={brightness}, blur_variance={blur_var}, edge_density={edge_density},\n"
            f"  entropy={entropy}, screenshot_score={screenshot_score}, pixels={int(pixels)},\n"
            f"  is_thumbnail={is_thumb}, exif_missing={exif_bad}\n"
            f"Issues detected: {issues or 'none'}\n"
            f"Verdict: {verdict}"
        )
    finally:
        db.close()


@tool
def estimate_photo_quality_deep(photo_id: int) -> str:
    """
    Run a deep AI-based quality assessment using the CLIP vision model.
    ⏳ Slow — requires running a neural network. Use sparingly.

    Compares the photo against 8 quality-related text probes using cosine similarity.
    Returns similarity score per probe (0–1) and an overall verdict.

    Read-only — no changes are made.

    User query examples:
    - "Use AI to check if photo 7 is garbage"
    - "Do a deep analysis of picture 15"
    - "Run the AI quality check on photo 3"
    - "Сделай глубокий анализ качества фото 10"
    - "AI-проверка: хорошее ли фото 5?"
    """
    import numpy as np
    logger.info(f"[tool] estimate_photo_quality_deep: {photo_id}")
    db = SessionLocal()
    try:
        photo = get_photo_by_id(db, photo_id)
        if not photo:
            return f"Photo {photo_id} not found."
        probes = [
            "a blurry photo",
            "a dark photo",
            "an overexposed photo",
            "a screenshot",
            "a thumbnail or icon",
            "a flat featureless image",
            "a good quality photo",
            "a sharp well-lit photo",
        ]
        from PIL import Image
        with Image.open(photo.file_path) as img:
            img_rgb = img.convert("RGB")
            image_features = registry.clip_tagger.model.encode_image(img_rgb)
        image_vec = np.array(image_features).flatten()
        image_vec = image_vec / (np.linalg.norm(image_vec) + 1e-8)
        scores = {}
        for probe in probes:
            text_features = registry.clip_tagger.model.encode_text(probe)
            text_vec = np.array(text_features).flatten()
            text_vec = text_vec / (np.linalg.norm(text_vec) + 1e-8)
            scores[probe] = round(float(np.dot(image_vec, text_vec)), 4)
        bad_probes = probes[:6]
        good_probes = probes[6:]
        max_bad = max(scores[p] for p in bad_probes)
        max_good = max(scores[p] for p in good_probes)
        verdict = "likely garbage" if max_bad > max_good else "good quality"
        lines = [f"Photo {photo_id} deep quality assessment (CLIP):"]
        for probe, score in scores.items():
            lines.append(f"  {probe!r}: {score:.4f}")
        lines.append(f"Verdict: {verdict} (best bad={max_bad:.4f}, best good={max_good:.4f})")
        return "\n".join(lines)
    finally:
        db.close()


@tool
def get_photo_visual_metrics(photo_id: int) -> str:
    """
    Return raw visual measurements for a photo without any garbage judgment.

    Metrics: brightness, blur_variance, edge_density, entropy, colorfulness,
    width, height, resolution_mpx.

    Read-only — no changes are made.

    User query examples:
    - "How bright is photo 5?"
    - "What are the visual stats for picture 3?"
    - "Show me the sharpness and brightness of photo 7"
    - "Is photo 10 colourful?"
    - "Какая яркость у фото номер 4?"
    - "Покажи технические параметры снимка 9"
    """
    from src.quality_checks import get_visual_metrics
    logger.info(f"[tool] get_photo_visual_metrics: {photo_id}")
    db = SessionLocal()
    try:
        photo = get_photo_by_id(db, photo_id)
        if not photo:
            return f"Photo {photo_id} not found."
        metrics = get_visual_metrics(photo.file_path)
        lines = [f"Visual metrics for photo {photo_id}:"]
        for k, v in metrics.items():
            lines.append(f"  {k}: {v}")
        return "\n".join(lines)
    finally:
        db.close()


# =============================================================================
# Group B — Duplicate Comparison
# =============================================================================

@tool
def compare_photos_quick(photo_id_a: int, photo_id_b: int) -> str:
    """
    Compare two photos using perceptual hashing (dHash, aHash, pHash).
    Fast — no AI model required, runs in milliseconds.

    If a photo's hash is not yet stored in the database, it is computed on the fly
    and saved automatically for future comparisons.

    Returns Hamming distances (0 = identical, higher = more different) and a verdict.
    Duplicate threshold: dHash distance ≤ 10.

    Read-only comparison — no photos are moved or deleted.

    User query examples:
    - "Are photos 5 and 8 the same?"
    - "Is picture 12 a duplicate of picture 7?"
    - "Compare photo number 3 and photo number 9"
    - "These two look the same — check them"
    - "Это одно и то же фото?"
    - "Сравни фото 4 и фото 11"
    """
    import imagehash
    from PIL import Image
    logger.info(f"[tool] compare_photos_quick: {photo_id_a} vs {photo_id_b}")
    db = SessionLocal()
    try:
        photo_a = get_photo_by_id(db, photo_id_a)
        photo_b = get_photo_by_id(db, photo_id_b)
        if not photo_a:
            return f"Photo {photo_id_a} not found."
        if not photo_b:
            return f"Photo {photo_id_b} not found."

        def _ensure_hashes(photo):
            from src.db_service import _hamming_distance
            from src.models import PhotoHash as PH
            ph = db.query(PH).filter_by(photo_id=photo.id).first()
            if ph and ph.dhash:
                return ph
            with Image.open(photo.file_path) as img:
                d = str(imagehash.dhash(img))
                a = str(imagehash.average_hash(img))
                p = str(imagehash.phash(img))
            return get_or_create_photo_hash(db, photo.id, dhash=d, ahash=a, phash=p)

        ha = _ensure_hashes(photo_a)
        hb = _ensure_hashes(photo_b)

        from src.db_service import _hamming_distance
        dist_d = _hamming_distance(ha.dhash, hb.dhash)
        dist_a = _hamming_distance(ha.ahash, hb.ahash)
        dist_p = _hamming_distance(ha.phash, hb.phash)
        verdict = "likely duplicates" if dist_d <= 10 else "probably different"
        return (
            f"Comparison: photo {photo_id_a} vs photo {photo_id_b}\n"
            f"  dHash distance: {dist_d} (threshold ≤ 10)\n"
            f"  aHash distance: {dist_a}\n"
            f"  pHash distance: {dist_p}\n"
            f"Verdict: {verdict}"
        )
    finally:
        db.close()


@tool
def compare_photos_deep(photo_id_a: int, photo_id_b: int) -> str:
    """
    Compare two photos using the CLIP vision model (cosine similarity).
    ⏳ Slow — requires encoding both images with a neural network.

    Returns a similarity score 0–1 (1 = identical, >0.9 = very similar).
    Use when compare_photos_quick is inconclusive or when photos are
    different crops, resizes, or colour-graded versions of the same shot.

    Read-only — no photos are moved or deleted.

    User query examples:
    - "Do a deep check — are photos 5 and 8 really duplicates?"
    - "Use AI to compare picture 3 and picture 10"
    - "These two look almost the same — AI check please"
    - "Сделай глубокое сравнение фото 6 и фото 14"
    - "Проверь с помощью AI: одинаковые ли фото 2 и 9?"
    """
    import numpy as np
    from PIL import Image
    logger.info(f"[tool] compare_photos_deep: {photo_id_a} vs {photo_id_b}")
    db = SessionLocal()
    try:
        photo_a = get_photo_by_id(db, photo_id_a)
        photo_b = get_photo_by_id(db, photo_id_b)
        if not photo_a:
            return f"Photo {photo_id_a} not found."
        if not photo_b:
            return f"Photo {photo_id_b} not found."

        def _encode(fp):
            with Image.open(fp) as img:
                feats = registry.clip_tagger.model.encode_image(img.convert("RGB"))
            vec = np.array(feats).flatten()
            return vec / (np.linalg.norm(vec) + 1e-8)

        vec_a = _encode(photo_a.file_path)
        vec_b = _encode(photo_b.file_path)
        similarity = round(float(np.dot(vec_a, vec_b)), 4)
        if similarity >= 0.95:
            verdict = "almost certainly duplicates"
        elif similarity >= 0.85:
            verdict = "very similar — likely duplicates"
        elif similarity >= 0.70:
            verdict = "somewhat similar"
        else:
            verdict = "probably different"
        return (
            f"CLIP similarity: photo {photo_id_a} vs photo {photo_id_b}\n"
            f"  Cosine similarity: {similarity:.4f}\n"
            f"Verdict: {verdict}"
        )
    finally:
        db.close()


# =============================================================================
# Group C — Annotation (all write — all require user confirmation)
# =============================================================================

@tool
def add_tag_to_photos(photo_ids: List[int], tag_name: str) -> str:
    """
    Add a tag to one or more photos in the database.
    If the tag does not exist yet, it is created automatically.
    Confidence score is set to 1.0 (manually assigned = certain).

    ⚠️ BEFORE CALLING THIS TOOL — ASK USER PERMISSION:
    Tell the user: "I am going to add the tag '[tag_name]' to [N] photo(s) (IDs: ...)."
    Ask: "Should I go ahead?"
    Only call after confirmation.

    Saves a history action — can be undone with undo_last_action.

    User query examples:
    - "Tag photos 3, 5 and 7 as sunset"
    - "Add the label 'family' to these pictures"
    - "Mark photo 10 with the tag 'vacation'"
    - "Put a 'nature' label on photo 4"
    - "Добавь тег 'природа' к фото 3 и 7"
    - "Пометь эти снимки как 'важное'"
    """
    logger.info(f"[tool] add_tag_to_photos: tag={tag_name!r} ids={photo_ids}")
    db = SessionLocal()
    try:
        tag = get_or_create_tag(db, tag_name)
        tagged = []
        for pid in photo_ids:
            photo = get_photo_by_id(db, pid)
            if not photo:
                continue
            add_photo_tag_with_score(db, pid, tag_name, score=1.0)
            tagged.append(pid)
        if tagged:
            create_history_action(
                db,
                action_type="add_tag",
                photo_ids=tagged,
                params={"tag_name": tag_name, "tag_id": tag.id},
                undo_data={"tag_id": tag.id, "tag_name": tag_name, "photo_ids": tagged},
            )
        skipped = len(photo_ids) - len(tagged)
        result = f"Added tag '{tag_name}' to {len(tagged)} photo(s)."
        if skipped:
            result += f" Skipped {skipped} (not found)."
        return result
    finally:
        db.close()


@tool
def add_category_to_photos(photo_ids: List[int], category_name: str) -> str:
    """
    Assign a category to one or more photos in the database.
    If the category does not exist yet, it is created automatically.
    Confidence score is set to 1.0 (manually assigned = certain).

    ⚠️ BEFORE CALLING THIS TOOL — ASK USER PERMISSION:
    Tell the user: "I am going to assign the category '[category_name]' to [N] photo(s) (IDs: ...)."
    Ask: "Should I go ahead?"
    Only call after confirmation.

    Saves a history action — can be undone with undo_last_action.

    User query examples:
    - "Put photo 5 in the Travel category"
    - "Categorize pictures 3 and 8 as Food"
    - "Assign the Nature category to photo 11"
    - "These photos are from the wedding — mark them as Events"
    - "Отнеси фото 2, 4, 6 к категории 'Семья'"
    - "Добавь фото 1 в категорию 'Природа'"
    """
    logger.info(f"[tool] add_category_to_photos: cat={category_name!r} ids={photo_ids}")
    db = SessionLocal()
    try:
        cat = get_or_create_category(db, category_name)
        assigned = []
        for pid in photo_ids:
            photo = get_photo_by_id(db, pid)
            if not photo:
                continue
            add_photo_category_with_score(db, pid, cat.id, score=1.0)
            assigned.append(pid)
        if assigned:
            create_history_action(
                db,
                action_type="add_category",
                photo_ids=assigned,
                params={"category_name": category_name, "category_id": cat.id},
                undo_data={"category_id": cat.id, "category_name": category_name, "photo_ids": assigned},
            )
        skipped = len(photo_ids) - len(assigned)
        result = f"Assigned category '{category_name}' to {len(assigned)} photo(s)."
        if skipped:
            result += f" Skipped {skipped} (not found)."
        return result
    finally:
        db.close()


@tool
def add_geoposition_to_photos(
    photo_ids: List[int],
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    address: Optional[str] = None,
) -> str:
    """
    Set the geographical location for one or more photos.

    Accepts either:
    - latitude + longitude → automatically reverse-geocodes to get the address
    - address (text) → forward-geocodes to get latitude and longitude

    ⚠️ BEFORE CALLING THIS TOOL — ASK USER PERMISSION:
    Tell the user: "I am going to set the location of [N] photo(s) to [address or coordinates]."
    Ask: "Should I go ahead?"
    Only call after confirmation.

    Saves a history action — can be undone with undo_last_action.
    Requires an internet connection for geocoding.

    User query examples:
    - "These photos are from Paris — set the location"
    - "Mark photos 3 and 7 as taken in Moscow"
    - "Set the location of photo 5 to 48.8566, 2.3522"
    - "These are from the Eiffel Tower area"
    - "Укажи для этих фото место съёмки: Санкт-Петербург"
    - "Поставь геолокацию для фото 8: Москва, Красная площадь"
    """
    from src.geo import GeoEnricher
    logger.info(f"[tool] add_geoposition_to_photos: ids={photo_ids} lat={latitude} lon={longitude} addr={address!r}")
    if latitude is None and longitude is None and not address:
        return "Error: provide either latitude+longitude or an address."
    db = SessionLocal()
    try:
        enricher = GeoEnricher()
        if address and (latitude is None or longitude is None):
            loc = enricher.geolocator.geocode(address)
            if not loc:
                return f"Error: could not geocode address '{address}'."
            latitude = loc.latitude
            longitude = loc.longitude
            resolved_address = loc.address
        else:
            resolved_address = enricher.reverse_geocode(latitude, longitude)
        original_geo_ids = {}
        updated = []
        for pid in photo_ids:
            photo = get_photo_by_id(db, pid)
            if not photo:
                continue
            original_geo_ids[str(pid)] = photo.geoposition_id
            update_photo_geoposition(db, pid, latitude, longitude, resolved_address)
            updated.append(pid)
        if updated:
            create_history_action(
                db,
                action_type="add_geoposition",
                photo_ids=updated,
                params={"latitude": latitude, "longitude": longitude, "address": resolved_address},
                undo_data={"original_geoposition_ids": original_geo_ids},
            )
        skipped = len(photo_ids) - len(updated)
        result = f"Set location '{resolved_address}' ({latitude:.5f}, {longitude:.5f}) for {len(updated)} photo(s)."
        if skipped:
            result += f" Skipped {skipped} (not found)."
        return result
    finally:
        db.close()


@tool
def geocode_photo_from_exif(photo_id: int) -> str:
    """
    Read GPS coordinates from a photo's EXIF data and save the detected location
    to the database via reverse geocoding.

    ⚠️ BEFORE CALLING THIS TOOL — ASK USER PERMISSION:
    Tell the user: "I am going to read the GPS data from photo [photo_id]'s EXIF
    and save the detected location to the database."
    Ask: "Should I go ahead?"
    Only call after confirmation.

    Requires an internet connection. If the photo has no GPS data, returns an error.

    User query examples:
    - "Find out where photo 5 was taken"
    - "Get the location from the EXIF of picture 12"
    - "Read the GPS from photo 7 and save it"
    - "Where was photo number 3 shot? Check the EXIF"
    - "Определи место съёмки фото 9 по EXIF"
    - "Сохрани геолокацию фото 6 из метаданных"
    """
    from src.geo import GeoEnricher
    from src.metadata import get_exif_data as _exif_fn
    logger.info(f"[tool] geocode_photo_from_exif: {photo_id}")
    db = SessionLocal()
    try:
        photo = get_photo_by_id(db, photo_id)
        if not photo:
            return f"Photo {photo_id} not found."
        exif_raw = _exif_fn(photo.file_path)
        enricher = GeoEnricher()
        geo = enricher.geocode_photo(exif_raw)
        if not geo.get("latitude") or not geo.get("longitude"):
            return f"Photo {photo_id} has no GPS data in EXIF."
        update_photo_geoposition(db, photo_id, geo["latitude"], geo["longitude"], geo.get("address"))
        return (
            f"Geocoded photo {photo_id}: lat={geo['latitude']:.5f}, "
            f"lon={geo['longitude']:.5f}, address='{geo.get('address')}'"
        )
    finally:
        db.close()


# =============================================================================
# Group D — Search & Filter
# =============================================================================

@tool
def get_photos_by_tag_id(tag_id: int) -> str:
    """
    Return all photos that have a specific tag (identified by its numeric ID).

    Read-only — no changes are made.
    Use get_tags first if you need to find a tag's ID from its name.

    User query examples:
    - "Show all photos tagged as sunset"  ← first call get_tags to get the ID
    - "Find photos with tag number 3"
    - "List all pictures labelled 'family'"
    - "Which photos have the 'vacation' tag?"
    - "Покажи все фото с тегом 'природа'"
    - "Фотографии с меткой 5"
    """
    logger.info(f"[tool] get_photos_by_tag_id: {tag_id}")
    db = SessionLocal()
    try:
        photos = _get_photos_by_tag_id(db, tag_id)
        if not photos:
            return f"No photos found with tag ID {tag_id}."
        return _serialize_photos(photos)
    finally:
        db.close()


@tool
def search_photos_by_exif(
    width_min: Optional[int] = None,
    width_max: Optional[int] = None,
    height_min: Optional[int] = None,
    height_max: Optional[int] = None,
    focal_length_min: Optional[float] = None,
    focal_length_max: Optional[float] = None,
    aperture_min: Optional[float] = None,
    aperture_max: Optional[float] = None,
    iso_min: Optional[int] = None,
    iso_max: Optional[int] = None,
    camera_make: Optional[str] = None,
    camera_model: Optional[str] = None,
    limit: int = 50,
) -> str:
    """
    Search for photos by technical camera parameters stored in EXIF data.

    All parameters are optional — combine any subset. Ranges are inclusive.
    camera_make and camera_model are case-insensitive partial matches.

    Read-only — no changes are made.

    User query examples:
    - "Find all photos taken with a wide angle lens"    (focal_length_max=35)
    - "Show photos taken at high ISO"                   (iso_min=3200)
    - "Pictures taken with an iPhone"                   (camera_make="apple")
    - "Find large photos — wider than 4000 pixels"      (width_min=4000)
    - "Photos shot wide open at f/1.8"                  (aperture_max=2.0)
    - "Show me shots from my Canon"                     (camera_make="canon")
    - "Найди фотографии с широкоугольным объективом"
    - "Покажи снимки с высоким ISO"
    - "Фото сделанные на Canon"
    """
    logger.info(f"[tool] search_photos_by_exif: {locals()}")
    db = SessionLocal()
    try:
        photos = search_photos_by_exif_params(
            db,
            width_min=width_min, width_max=width_max,
            height_min=height_min, height_max=height_max,
            focal_length_min=focal_length_min, focal_length_max=focal_length_max,
            aperture_min=aperture_min, aperture_max=aperture_max,
            iso_min=iso_min, iso_max=iso_max,
            camera_make=camera_make, camera_model=camera_model,
            limit=limit,
        )
        if not photos:
            return "No photos found matching those EXIF criteria."
        return _serialize_photos(photos)
    finally:
        db.close()


@tool
def filter_photos(
    category_ids: Optional[List[int]] = None,
    tag_ids: Optional[List[int]] = None,
    camera_id: Optional[int] = None,
    geoposition_id: Optional[int] = None,
    is_doc: Optional[bool] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    day: Optional[int] = None,
    limit: int = 50,
    skip: int = 0,
) -> str:
    """
    Filter photos using the same criteria available in the Gallery page of the app.

    All parameters are optional. Multiple category_ids or tag_ids require ALL
    of them to be present (AND logic). Prefer this over search_photos_metadata
    when date filters are needed.

    Read-only — no changes are made.

    User query examples:
    - "Show me photos from July 2023"               (year=2023, month=7)
    - "Find family photos taken in Paris"          (category_ids=[...], geoposition_id=...)
    - "Photos from my Nikon from last summer"      (camera_id=..., year=..., month=...)
    - "Document photos from 2022"                  (is_doc=True, year=2022)
    - "Show the first 20 nature photos"            (category_ids=[...], limit=20)
    - "Покажи фото за август 2021 года"
    - "Найди пейзажи сделанные в Москве"
    - "Фотографии документов за прошлый год"
    """
    logger.info(f"[tool] filter_photos: {locals()}")
    db = SessionLocal()
    try:
        photos, total = get_all_photos(
            db,
            category_ids=category_ids,
            tag_ids=tag_ids,
            camera_id=camera_id,
            geoposition_id=geoposition_id,
            is_doc=is_doc,
            year=year,
            month=month,
            day=day,
            skip=skip,
            limit=limit,
        )
        if not photos:
            return "No photos found matching those filters."
        return _serialize_photos(photos)
    finally:
        db.close()
