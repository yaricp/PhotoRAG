from loguru import logger
from typing import List, Optional
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.db_service import (
    get_photos_by_vector, get_all_photos, get_photo_by_id,
    get_all_categories, get_all_tags, get_all_cameras,
    get_all_geopositions, get_photos_by_category_id
)
from src.database import SessionLocal


class SearchMetadataArgs(BaseModel):
    category_ids: Optional[List[int]] = Field(None, description="Filter by category ID")
    tag_ids: Optional[List[int]] = Field(None, description="Filter by tag ID")
    geoposition_id: Optional[int] = Field(None, description="Filter by geoposition ID")
    camera_id: Optional[int] = Field(None, description="Filter by camera ID")
    is_doc: Optional[bool] = Field(None, description="Filter for document photos only")
    limit: int = Field(10, description="Maximum number of photos to return")


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
    A list of matching photos with ID, file path, and description.
    """
    logger.info(f"[tool] semantic search: {query}")
    db = SessionLocal()
    try:
        photos = get_photos_by_vector(db, query, k)
        if not photos:
            return "No photos found matching that description."
        
        results = []
        for p in photos:
            results.append(f"ID: {p.id} | Path: {p.file_path} | Description: {p.description}")
        return "\n".join(results)
    finally:
        db.close()


@tool
def search_photos_by_category_id(category_id: int) -> str:
    """
    Search for photos by category id.

    Use this tool when:
    - The user asks to filter photos by category id

    Returns:
    A list of matching photos with ID.
    """
    logger.info(f"[tool] category search: {category_id}")
    db = SessionLocal()
    try:
        photos = get_photos_by_category_id(db, category_id)
        if not photos:
            return "No photos found in this category."
        
        results = []
        for photo in photos:
            results.append(f"ID: {photo.id}")
        return "\n".join(results)
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
    A list of matching photos with ID only.
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
        
        results = []
        for p in photos:
            results.append(f"ID: {p.id}")
        return f"Found {total} photos (showing {len(photos)}):\n" + "\n".join(results)
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
    Detailed information including:
    - file path
    - description
    - OCR text (if available)
    - camera info
    - tags
    - categories
    """
    logger.info(f"[tool] photo details: {photo_id}")
    db = SessionLocal()
    try:
        p = get_photo_by_id(db, photo_id)
        if not p:
            return f"Photo with ID {photo_id} not found."
        
        details = [
            f"ID: {p.id}",
            f"File Path: {p.file_path}",
            f"Captured At: {p.captured_at}",
            f"Description: {p.description}",
            f"OCR Text: {p.ocr_text or 'None'}",
            f"Is Document: {p.is_doc}",
            f"Camera Make: {p.camera.make if p.camera else 'Unknown'}",
            f"Camera Model: {p.camera.model if p.camera else 'Unknown'}"
        ]
        
        tags = [pt.tag.name for pt in p.tags_rel]
        if tags:
            details.append(f"Tags: {', '.join(tags)}")
            
        categories = [pc.category.name for pc in p.categories_rel]
        if categories:
            details.append(f"Categories: {', '.join(categories)}")
            
        return "\n".join(details)
    finally:
        db.close()


@tool
def get_categories():
    """
    Get all categories.
    """
    logger.info(f"[tool] categories")
    db = SessionLocal()
    try:
        result = "Available Categories:\n"
        categories_db = get_all_categories(db)
        for category in categories_db:
            result += f"ID: {category.id} | Name: {category.name}\n"
        logger.info(f"[tool] categories result: {result}")
        return result
    finally:
        db.close()


@tool
def get_tags():
    """
    Get all tags.
    """
    db = SessionLocal()
    try:
        result = "Available Tags:\n"
        tags_db = get_all_tags(db)
        for tag in tags_db:
            result += f"ID: {tag.id} | Name: {tag.name}\n"
        logger.info(f"[tool] tags result: {result}")
        return result
    finally:
        db.close()


@tool
def get_cameras():
    """
    Get all cameras.
    """
    logger.info(f"[tool] cameras")
    db = SessionLocal()
    try:
        result = "Available Cameras:\n"
        cameras_db = get_all_cameras(db)
        for camera in cameras_db:
            result += f"ID: {camera.id} | Name: {camera.name}\n"
        logger.info(f"[tool] cameras result: {result}")
        return result
    finally:
        db.close()


@tool
def get_geopositions():
    """
    Get all geoposition.
    """
    logger.info(f"[tool] geoposition")
    db = SessionLocal()
    try:
        result = "Available Geoposition:\n"
        geopositions_db = get_all_geopositions(db)
        for geoposition in geopositions_db:
            result += f"ID: {geoposition.id} | Name: {geoposition.name}\n"
        logger.info(f"[tool] geoposition result: {result}")
        return result
    finally:
        db.close()

