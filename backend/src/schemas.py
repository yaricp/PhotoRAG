from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional, Generic, TypeVar, List
from datetime import datetime
from enum import Enum

T = TypeVar('T')


class Watcher(BaseModel):
    id: int
    path: str
    status: str
    destination_path: str
    
    model_config = ConfigDict(from_attributes=True)


class WatchRequest(BaseModel):
    path: str
    destination_path: str


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
    is_trash: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


class QueryRequest(BaseModel):
    text_query: str = Field(..., min_length=1, max_length=200)
    k: int = Field(..., ge=10, le=100)
    thresholds: float = Field(..., ge=0.0, le=1.0)


class PhotoSearchResult(BaseModel):
    photo: "Photo"
    distance: float


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
    photos: List[Photo] = []


class Job(BaseModel):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    phase: Optional[str] = None
    tasks: Optional[str] = None
    photo_id: int
    file_path: str
    
    model_config = ConfigDict(from_attributes=True)


class FolderScannerProgress(BaseModel):
    id: int
    path: str
    progress: Optional[int] = None


class FolderScanner(BaseModel):
    id: int
    path: str
    total_steps: Optional[int] = None
    scanned_steps: Optional[int] = None
    
    model_config = ConfigDict(from_attributes=True)


class FolderScannerRequest(BaseModel):
    path: str


class AIModelConfigBase(BaseModel):
    mode: str
    model_name: str
    url: Optional[str] = None
    api_key: Optional[str] = None
    model_provider: Optional[str] = None
    similarity_limit: Optional[float] = None


class AIModelConfigUpdate(AIModelConfigBase):
    pass


class AIModelConfigResponse(AIModelConfigBase):
    id: int
    type: str

    model_config = ConfigDict(from_attributes=True)


class AppSettingSchema(BaseModel):
    key: str
    value: str

    model_config = ConfigDict(from_attributes=True)


class HistoryActionSchema(BaseModel):
    id: int
    action_type: str
    photo_ids: Optional[List[int]] = None
    params: dict
    undo_data: dict
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm_model(cls, action: "HistoryAction") -> "HistoryActionSchema":
        import json
        return cls(
            id=action.id,
            action_type=action.action_type,
            photo_ids=json.loads(action.photo_ids) if action.photo_ids else None,
            params=json.loads(action.params),
            undo_data=json.loads(action.undo_data),
            created_at=action.created_at,
        )


# ---------------------------------------------------------------------------
# Template Tags
# ---------------------------------------------------------------------------

class TemplateTagCreate(BaseModel):
    name: str
    clip_prompt: str

class TemplateTagUpdate(BaseModel):
    name: str
    clip_prompt: str

class TemplateTagResponse(BaseModel):
    id: int
    name: str
    clip_prompt: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

# ---------------------------------------------------------------------------
# Template Categories
# ---------------------------------------------------------------------------

class TemplateCategoryCreate(BaseModel):
    name: str
    clip_prompt: str

class TemplateCategoryUpdate(BaseModel):
    name: str
    clip_prompt: str

class TemplateCategoryResponse(BaseModel):
    id: int
    name: str
    clip_prompt: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

# Recompute status returned by write endpoints
class RecomputeStatus(BaseModel):
    status: str = "recomputing"

# ---------------------------------------------------------------------------
# Photo edit schemas
# ---------------------------------------------------------------------------

class PhotoUpdate(BaseModel):
    description: Optional[str] = None
    translated_description: Optional[str] = None
    ocr_text: Optional[str] = None

class PhotoFlagsUpdate(BaseModel):
    is_doc: Optional[bool] = None
    is_trash: Optional[bool] = None

class PhotoTagLink(BaseModel):
    name: str

class PhotoCategoryLink(BaseModel):
    name: str

class PhotoTagResponse(BaseModel):
    id: int
    name: str
    confidence_score: Optional[float] = None
    model_config = ConfigDict(from_attributes=True)

class PhotoCategoryResponse(BaseModel):
    id: int
    name: str
    confidence_score: Optional[float] = None
    model_config = ConfigDict(from_attributes=True)


class PipelineTaskSchema(BaseModel):
    id: int
    photo_id: int
    phase: str
    task_name: str
    status: str
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PromptResponse(BaseModel):
    id: int
    key: str
    group: str
    name: str
    title: str
    text: str
    description: Optional[str] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class PromptUpdate(BaseModel):
    text: str

    @field_validator("text")
    @classmethod
    def text_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("text must not be blank")
        return v

