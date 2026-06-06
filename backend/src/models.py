from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

try:
    from pgvector.sqlalchemy import Vector  # noqa: F401
except ImportError:
    pass


Base = declarative_base()


class PhotoTag(Base):
    __tablename__ = "photo_tags"
    photo_id = Column(Integer, ForeignKey("photos.id"), primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.id"), primary_key=True)
    confidence_score = Column(Float, default=0.0)
    photo = relationship("Photo", back_populates="tags_rel")
    tag = relationship("Tag", back_populates="photos")


class PhotoCategory(Base):
    __tablename__ = "photo_categories"
    photo_id = Column(Integer, ForeignKey("photos.id"), primary_key=True)
    category_id = Column(Integer, ForeignKey("categories.id"), primary_key=True)
    confidence_score = Column(Float, default=0.0)
    photo = relationship("Photo", back_populates="categories_rel")
    category = relationship("Category", back_populates="photos")


photo_persons = Table(
    "photo_persons",
    Base.metadata,
    Column("photo_id", Integer, ForeignKey("photos.id"), primary_key=True),
    Column("person_id", Integer, ForeignKey("persons.id"), primary_key=True),
)


photo_keywords = Table(
    "photo_keywords",
    Base.metadata,
    Column("photo_id", Integer, ForeignKey("photos.id"), primary_key=True),
    Column("keyword_id", Integer, ForeignKey("keywords.id"), primary_key=True),
)


class Photo(Base):
    __tablename__ = "photos"

    id = Column(Integer, primary_key=True)
    hash = Column(String, unique=True, index=True)
    file_path = Column(String, index=True)

    exif_data = Column(JSON, nullable=True)
    keywords = Column(JSON, nullable=True)
    ocr_text = Column(String, nullable=True)
    description = Column(String, nullable=True)
    translated_description = Column(String, nullable=True)
    is_doc = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False)
    image_width = Column(Integer, nullable=True)
    image_height = Column(Integer, nullable=True)
    iso = Column(Integer, nullable=True)
    aperture = Column(Float, nullable=True)
    focal_length = Column(Float, nullable=True)
    shutter_speed = Column(Float, nullable=True)
    offset_time = Column(String, nullable=True)

    file_created_at = Column(DateTime, nullable=True)
    captured_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=True)
    camera = relationship("Camera", back_populates="photos")

    geoposition_id = Column(Integer, ForeignKey("geopositions.id"), nullable=True)
    geoposition = relationship("Geoposition", back_populates="photos")

    tags_rel = relationship("PhotoTag", back_populates="photo", cascade="all, delete-orphan")
    categories_rel = relationship("PhotoCategory", back_populates="photo", cascade="all, delete-orphan")

    persons_rel = relationship("Person", secondary=photo_persons, back_populates="photos")
    keywords_rel = relationship("Keyword", secondary=photo_keywords, back_populates="photos")
    job_rel = relationship("ProcessingJob", back_populates="photo", uselist=False)

    photo_hash = relationship("PhotoHash", back_populates="photo", uselist=False, cascade="all, delete-orphan")
    duplicates_as_original = relationship(
        "PhotoDuplicate",
        foreign_keys="PhotoDuplicate.original_photo_id",
        back_populates="original_photo",
        cascade="all, delete-orphan",
    )
    duplicates_as_duplicate = relationship(
        "PhotoDuplicate",
        foreign_keys="PhotoDuplicate.duplicate_photo_id",
        back_populates="duplicate_photo",
        cascade="all, delete-orphan",
    )
    quality_issues = relationship("PhotoQualityIssue", back_populates="photo", cascade="all, delete-orphan")


class PhotoEmbedding(Base):
    __tablename__ = "photo_embedding_map"

    id = Column(Integer, primary_key=True)
    photo_id = Column(Integer, ForeignKey("photos.id"), index=True)
    model = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    prompt = Column(String, nullable=True)
    photos = relationship("PhotoCategory", back_populates="category")


class Tag(Base):
    __tablename__ = "tags"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    photos = relationship("PhotoTag", back_populates="tag")


class Camera(Base):
    __tablename__ = "cameras"
    id = Column(Integer, primary_key=True)
    make = Column(String)
    model = Column(String)
    serial_number = Column(String, nullable=True)
    photos = relationship("Photo", back_populates="camera")


class Geoposition(Base):
    __tablename__ = "geopositions"
    id = Column(Integer, primary_key=True)
    latitude = Column(Float)
    longitude = Column(Float)
    address = Column(String, nullable=True)
    photos = relationship("Photo", back_populates="geoposition")


class Person(Base):
    __tablename__ = "persons"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    photos = relationship("Photo", secondary=photo_persons, back_populates="persons_rel")


class Keyword(Base):
    __tablename__ = "keywords"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    photos = relationship("Photo", secondary=photo_keywords, back_populates="keywords_rel")


class ModelState(Base):
    __tablename__ = "model_states"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    status = Column(String, default="pending")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Watcher(Base):
    __tablename__ = "watchers"
    id = Column(Integer, primary_key=True)
    path = Column(String, unique=True)
    destination_path = Column(String, nullable=True)
    status = Column(String, default="pending")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    phase = Column(String)
    photo_id = Column(Integer, ForeignKey("photos.id"), unique=True)
    tasks = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    photo = relationship("Photo", back_populates="job_rel")


class FolderScanner(Base):
    __tablename__ = "folder_scanners"
    id = Column(Integer, primary_key=True)
    path = Column(String, unique=True)
    total_steps = Column(Integer, default=0)
    scanned_steps = Column(Integer, default=0)


class AIModelConfig(Base):
    __tablename__ = "ai_model_configs"
    id = Column(Integer, primary_key=True, index=True)
    type = Column(String, unique=True, index=True)  # e.g. 'vision', 'clip', 'embedding', 'translator', 'chat', 'ocr'
    mode = Column(String, default="local")  # "local" or "remote"
    model_name = Column(String)  # e.g. "Qwen/Qwen2-VL-2B-Instruct"
    url = Column(String, nullable=True)
    api_key = Column(String, nullable=True)
    model_provider = Column(String, nullable=True)  # e.g. "openai", "google_genai", "anthropic"
    similarity_limit = Column(Float, nullable=True)  # per-model L2 distance cutoff for vector search


class PhotoHash(Base):
    __tablename__ = "photo_hashes"
    id = Column(Integer, primary_key=True)
    photo_id = Column(Integer, ForeignKey("photos.id", ondelete="CASCADE"), unique=True, nullable=False)
    dhash = Column(String(16), nullable=True)
    ahash = Column(String(16), nullable=True)
    phash = Column(String(16), nullable=True)

    photo = relationship("Photo", back_populates="photo_hash")


class PhotoDuplicate(Base):
    __tablename__ = "photo_duplicates"
    id = Column(Integer, primary_key=True)
    original_photo_id = Column(Integer, ForeignKey("photos.id", ondelete="CASCADE"), nullable=False)
    # exact duplicates: same SHA256, file was never ingested → store path only
    duplicate_file_path = Column(String, nullable=True)
    # perceptual duplicates: both photos are ingested → store photo_id reference
    duplicate_photo_id = Column(Integer, ForeignKey("photos.id", ondelete="CASCADE"), nullable=True)
    match_type = Column(String, nullable=False)  # 'exact' or 'perceptual'
    hash_distance = Column(Integer, nullable=True)

    original_photo = relationship("Photo", foreign_keys=[original_photo_id], back_populates="duplicates_as_original")
    duplicate_photo = relationship("Photo", foreign_keys=[duplicate_photo_id], back_populates="duplicates_as_duplicate")


class PhotoQualityIssue(Base):
    __tablename__ = "photo_quality_issues"

    id = Column(Integer, primary_key=True)
    photo_id = Column(Integer, ForeignKey("photos.id", ondelete="CASCADE"), nullable=False, index=True)
    issue_type = Column(String, nullable=False)
    score = Column(Float, nullable=True)
    detected_at = Column(DateTime, default=datetime.utcnow)

    photo = relationship("Photo", back_populates="quality_issues")


class TemplateTag(Base):
    __tablename__ = "template_tags"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    clip_prompt = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TemplateCategory(Base):
    __tablename__ = "template_categories"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    clip_prompt = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key = Column(String, primary_key=True)
    value = Column(String, nullable=False, default="")


class HistoryAction(Base):
    __tablename__ = "history_actions"

    id = Column(Integer, primary_key=True)
    action_type = Column(String, nullable=False)
    photo_ids = Column(String, nullable=True)  # JSON list[int]
    params = Column(String, nullable=False)  # JSON dict
    undo_data = Column(String, nullable=False)  # JSON dict
    created_at = Column(DateTime, default=datetime.utcnow)


class PipelineTask(Base):
    """Per-task progress record for the Processing Page."""

    __tablename__ = "pipeline_tasks"

    id = Column(Integer, primary_key=True)
    photo_id = Column(Integer, ForeignKey("photos.id", ondelete="CASCADE"), nullable=False, index=True)
    phase = Column(String, nullable=False)
    task_name = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending")  # pending|running|done|failed
    error = Column(String, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Prompt(Base):
    """Editable AI prompts, seeded from prompts/prompts.json."""

    __tablename__ = "prompts"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, nullable=False, index=True)  # "vision_analysis.describe_scene"
    group = Column(String, nullable=False)  # "vision_analysis"
    name = Column(String, nullable=False)  # "describe_scene"
    title = Column(String, nullable=False)  # Human-readable label for the UI
    text = Column(Text, nullable=False)  # The actual prompt text
    description = Column(String, nullable=True)  # Usage hint shown in UI
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
