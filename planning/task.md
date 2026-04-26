# Phase 1: Core Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Initialize the FastAPI backend, configure the PostgreSQL vector database models, and build the Tier 1 synchronous file watcher that logs new photos instantly.

**Architecture:** We use FastAPI, SQLAlchemy (with pgvector), and Watchdog. The watcher detects files and commits basic metadata so the frontend can query it before heavy AI inference.

**Tech Stack:** Python 3.10+, FastAPI, Uvicorn, PostgreSQL, SQLAlchemy, pgvector, watchdog, pytest.

---

### Task 1: Environment & Project Scaffolding

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/src/config.py`
- Test: `backend/tests/test_config.py`

- [ ] **Step 1: Write the failing test for configuration mapping**
```python
# backend/tests/test_config.py
import os
from src.config import Settings

def test_settings_loads_env_vars(monkeypatch):
    monkeypatch.setenv("VISION_DESCRIBER_MODEL", "Qwen/test-model")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/testdb")
    settings = Settings()
    assert settings.VISION_DESCRIBER_MODEL == "Qwen/test-model"
    assert settings.DATABASE_URL == "postgresql://user:pass@localhost:5432/testdb"
```
- [ ] **Step 2: Run test to verify it fails**
Run: `pytest backend/tests/test_config.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src'"

- [ ] **Step 3: Write minimal implementation**
```python
# backend/src/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    VISION_DESCRIBER_MODEL: str = "Qwen/Qwen2-VL-2B-Instruct"
    PHOTO_EMBEDDER_MODEL: str = "nomic-ai/nomic-embed-text-v1.5"
    DATABASE_URL: str = "postgresql://user:pass@localhost:5432/photodb"
    
    class Config:
        env_file = ".env"
```
- [ ] **Step 4: Run test to verify it passes**
Run: `pytest backend/tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add backend/tests/test_config.py backend/src/config.py
git commit -m "feat: setup environment configuration loading"
```

### Task 2: Database Schema (SQLAlchemy + pgvector)

**Files:**
- Create: `backend/src/database.py`
- Create: `backend/src/models.py`
- Test: `backend/tests/test_models.py`

- [ ] **Step 1: Write failing test for Photo model creation**
```python
# backend/tests/test_models.py
from src.models import Photo
from datetime import datetime

def test_photo_model_instantiation():
    photo = Photo(file_path="/test/path.jpg", hash="12345", status="pending")
    assert photo.file_path == "/test/path.jpg"
    assert photo.status == "pending"
```
- [ ] **Step 2: Run test to verify it fails**
Run: `pytest backend/tests/test_models.py -v`
Expected: FAIL 

- [ ] **Step 3: Write minimal implementation**
```python
# backend/src/models.py
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
    created_at = Column(DateTime, default=datetime.utcnow)
```
- [ ] **Step 4: Run test to verify it passes**
Run: `pytest backend/tests/test_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add backend/tests/test_models.py backend/src/models.py
git commit -m "feat: create Photo database model with pgvector mapping"
```

### Task 3: Tier 1 Fast File Watcher (Watchdog)

**Files:**
- Create: `backend/src/watcher.py`
- Test: `backend/tests/test_watcher.py`

- [ ] **Step 1: Write failing test for hash generation and file detection logic**
```python
# backend/tests/test_watcher.py
import tempfile
import os
from src.watcher import generate_file_hash, process_new_file

def test_generate_file_hash():
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"test data")
        temp_name = f.name
    
    file_hash = generate_file_hash(temp_name)
    os.remove(temp_name)
    assert file_hash == "916f0027a575074ce72a331777c3478d6513f786a591bd892da1a577bf2335f9" # SHA256 of "test data"
```
- [ ] **Step 2: Run test to verify it fails**
Run: `pytest backend/tests/test_watcher.py -v`
Expected: FAIL 

- [ ] **Step 3: Write minimal implementation**
```python
# backend/src/watcher.py
import hashlib

def generate_file_hash(filepath: str) -> str:
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def process_new_file(filepath: str):
    # Dummy placeholder for integrating with DB next step
    pass
```
- [ ] **Step 4: Run test to verify it passes**
Run: `pytest backend/tests/test_watcher.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add backend/tests/test_watcher.py backend/src/watcher.py
git commit -m "feat: implement precise file hashing for Tier 1 ingestion"
```
