from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Generic, TypeVar, List
from datetime import datetime

T = TypeVar('T')


class Watcher(BaseModel):
    id: int
    path: str
    status: str
    
    model_config = ConfigDict(from_attributes=True)


class WatchRequest(BaseModel):
    path: str


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


class GeoPosition(BaseModel):
    id: int
    photo_id: int
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class Photo(BaseModel):
    id: int
    hash: Optional[str] = None
    file_path: str
    created_at: Optional[datetime] = None
    captured_at: Optional[datetime] = None
    file_created_at: Optional[datetime] = None
    description: Optional[str] = None
    translated_description: Optional[str] = None
    tags_rel: Optional[list[PhotoTag]] = None
    categories_rel: Optional[list[PhotoCategory]] = None
    camera: Optional[Camera] = None
    geoposition: Optional[GeoPosition] = None
    is_doc: Optional[bool] = None
    ocr_text: Optional[str] = None
    image_width: Optional[int] = None
    image_height: Optional[int] = None
    iso: Optional[int] = None
    aperture: Optional[float] = None
    focal_length: Optional[float] = None
    shutter_speed: Optional[float] = None
    offset_time: Optional[str] = None
    keywords: Optional[list[str]] = None

    model_config = ConfigDict(from_attributes=True)


class QueryRequest(BaseModel):
    text_query: str = Field(..., min_length=1, max_length=200)
    k: int = Field(..., ge=10, le=100)
    thresholds: float = Field(..., ge=0.0, le=1.0)


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    size: int


class TranslateRequest(BaseModel):
    text: str
    src_lang: str = "eng_Latn"
    tgt_lang: str = "rus_Cyrl"


class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default"


class ChatResponse(BaseModel):
    response: str
    thread_id: str


class Job(BaseModel):
    id: int
    photo_id: int
    status: str
    
    model_config = ConfigDict(from_attributes=True)