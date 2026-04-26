from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.orm import declarative_base
from datetime import datetime
from pgvector.sqlalchemy import Vector

Base = declarative_base()

class Photo(Base):
    __tablename__ = "photos"
    
    id = Column(Integer, primary_key=True, index=True)
    file_path = Column(String, unique=True, index=True)
    hash = Column(String, unique=True, index=True)
    status = Column(String, default="pending")  # pending, embedded, complete
    exif_data = Column(JSON, nullable=True)
    keywords = Column(JSON, nullable=True)  # Populated via OpenCLIP
    ocr_text = Column(String, nullable=True)
    description = Column(String, nullable=True)  # Populated via Qwen2
    embedding = Column(Vector(768), nullable=True)  # Populated via nomic
    file_created_at = Column(DateTime, nullable=True) # File system time (Sync)
    captured_at = Column(DateTime, nullable=True) # EXIF capture time (Async)
    created_at = Column(DateTime, default=datetime.utcnow)
