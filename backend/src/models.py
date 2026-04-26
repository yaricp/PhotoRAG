from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey, Table, Float
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    # Fallback for environments without pgvector (like our unit tests)
    from sqlalchemy import JSON as Vector

Base = declarative_base()

# Association Tables for Many-to-Many
photo_tags = Table(
    'photo_tags', Base.metadata,
    Column('photo_id', Integer, ForeignKey('photos.id'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tags.id'), primary_key=True)
)

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

photo_categories = Table(
    'photo_categories', Base.metadata,
    Column('photo_id', Integer, ForeignKey('photos.id'), primary_key=True),
    Column('category_id', Integer, ForeignKey('categories.id'), primary_key=True)
)

class Photo(Base):
    __tablename__ = "photos"

    id = Column(Integer, primary_key=True)
    hash = Column(String, unique=True, index=True)
    file_path = Column(String, index=True)
    
    # Existing metadata blobs (for raw data)
    exif_data = Column(JSON, nullable=True)
    keywords = Column(JSON, nullable=True) 
    ocr_text = Column(String, nullable=True)
    description = Column(String, nullable=True)
    embedding = Column(Vector(768), nullable=True)
    
    file_created_at = Column(DateTime, nullable=True)
    captured_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    camera_id = Column(Integer, ForeignKey('cameras.id'), nullable=True)
    camera = relationship("Camera", back_populates="photos")
    
    geoposition = relationship("Geoposition", back_populates="photo", uselist=False)
    
    tags_rel = relationship("Tag", secondary=photo_tags, back_populates="photos")
    persons_rel = relationship("Person", secondary=photo_persons, back_populates="photos")
    keywords_rel = relationship("Keyword", secondary=photo_keywords, back_populates="photos")
    categories_rel = relationship("Category", secondary=photo_categories, back_populates="photos")

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

class Tag(Base):
    __tablename__ = "tags"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    photos = relationship("Photo", secondary=photo_tags, back_populates="tags_rel")

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

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    photos = relationship("Photo", secondary=photo_categories, back_populates="categories_rel")

class ModelState(Base):
    __tablename__ = "model_states"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    status = Column(String, default="pending")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
