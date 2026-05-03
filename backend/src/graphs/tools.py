from loguru import logger
from typing import List, Optional
from langchain_core.tools import tool
from src.db_service import get_photos_by_vector, get_all_photos, get_photo_by_id
from src.database import SessionLocal
from pydantic import BaseModel, Field

class SearchMetadataArgs(BaseModel):
    category_id: Optional[int] = Field(None, description="Filter by category ID")
    tag_id: Optional[int] = Field(None, description="Filter by tag ID")
    camera_id: Optional[int] = Field(None, description="Filter by camera ID")
    is_doc: Optional[bool] = Field(None, description="Filter for document photos only")
    limit: int = Field(10, description="Maximum number of photos to return")

@tool
def search_photos_semantic(query: str, k: int = 5) -> str:
    """
    Search for photos using natural language (semantic search).
    Example: 'Find photos of cats playing in the garden'
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
def search_photos_metadata(
    category_id: Optional[int] = None,
    tag_id: Optional[int] = None,
    camera_id: Optional[int] = None,
    is_doc: Optional[bool] = None,
    limit: int = 10
) -> str:
    """
    Search for photos using structured filters like category, tags, or camera.
    """
    db = SessionLocal()
    try:
        photos, total = get_all_photos(
            db, 
            category_id=category_id, 
            tag_id=tag_id, 
            camera_id=camera_id, 
            is_doc=is_doc,
            limit=limit
        )
        if not photos:
            return "No photos found matching these criteria."
        
        results = []
        for p in photos:
            results.append(f"ID: {p.id} | Path: {p.file_path} | Description: {p.description}")
        return f"Found {total} photos (showing {len(photos)}):\n" + "\n".join(results)
    finally:
        db.close()

@tool
def get_photo_details(photo_id: int) -> str:
    """
    Get detailed information about a specific photo by its ID, including OCR text and technical metadata.
    """
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
