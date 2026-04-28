from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class Camera(BaseModel):
    id: int
    make: str
    model: str
    serial_number: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class Category(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class PhotoCategory(BaseModel):
    confidence_score: Optional[float] = None
    category: Optional[Category] = None

    model_config = ConfigDict(from_attributes=True)


class Tag(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class PhotoTag(BaseModel):
    confidence_score: Optional[float] = None
    tag: Optional[Tag] = None

    model_config = ConfigDict(from_attributes=True)


class Photo(BaseModel):
    id: int
    hash: Optional[str] = None
    file_path: str
    captured_at: Optional[datetime] = None
    description: Optional[str] = None
    tags_rel: Optional[list[PhotoTag]] = None
    categories_rel: Optional[list[PhotoCategory]] = None
    camera: Optional[Camera] = None

    model_config = ConfigDict(from_attributes=True)
