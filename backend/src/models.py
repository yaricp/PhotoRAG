from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey, Table, Float, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    from sqlalchemy import JSON as Vector


Base = declarative_base()


class PhotoTag(Base):
    __tablename__ = 'photo_tags'
    photo_id = Column(Integer, ForeignKey('photos.id'), primary_key=True)
    tag_id = Column(Integer, ForeignKey('tags.id'), primary_key=True)
    confidence_score = Column(Float, default=0.0)
    photo = relationship("Photo", back_populates="tags_rel")
    tag = relationship("Tag", back_populates="photos")


class PhotoCategory(Base):
    __tablename__ = 'photo_categories'
    photo_id = Column(Integer, ForeignKey('photos.id'), primary_key=True)
    category_id = Column(Integer, ForeignKey('categories.id'), primary_key=True)
    confidence_score = Column(Float, default=0.0)
    photo = relationship("Photo", back_populates="categories_rel")
    category = relationship("Category", back_populates="photos")


photo_persons = Table(
    'photo_persons', Base.metadata,
    Column('photo_id', Integer, ForeignKey('photos.id'), primary_key=True),
    Column('person_id', Integer, ForeignKey('persons.id'), primary_key=True)
)


photo_keywords = Table(
    'photo_keywords', Base.metadata,
    Column('photo_id', Integer, ForeignKey('photos.id'), primary_key=True),
    Column('keyword_id', Integer, ForeignKey('keywords.id'), primary_key=True)
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

    camera_id = Column(Integer, ForeignKey('cameras.id'), nullable=True)
    camera = relationship("Camera", back_populates="photos")
    
    geoposition = relationship("Geoposition", back_populates="photo", uselist=False)
    
    tags_rel = relationship("PhotoTag", back_populates="photo", cascade="all, delete-orphan")
    categories_rel = relationship("PhotoCategory", back_populates="photo", cascade="all, delete-orphan")
    
    persons_rel = relationship("Person", secondary=photo_persons, back_populates="photos")
    keywords_rel = relationship("Keyword", secondary=photo_keywords, back_populates="photos")


class PhotoEmbedding(Base):
    __tablename__ = "photo_embedding_map"

    id = Column(Integer, primary_key=True)
    photo_id = Column(Integer, ForeignKey("photos.id"), index=True)

    vss_rowid = Column(Integer, index=True)

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
    photo_id = Column(Integer, ForeignKey('photos.id'), unique=True)
    latitude = Column(Float)
    longitude = Column(Float)
    address = Column(String, nullable=True)
    photo = relationship("Photo", back_populates="geoposition")


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
    status = Column(String, default="pending")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"
    id = Column(Integer, primary_key=True)
    phase = Column(String)
    photo_id = Column(Integer, ForeignKey('photos.id'), unique=True)
    tasks = Column(String, nullable=True)
