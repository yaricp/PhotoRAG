# Phase 5.2: True Parallel Task Ingestion

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement 4 discrete, parallel Huey tasks dispatched from the observer to ensure maximum CPU utilization for AI enrichment.

---

### Task 1: Parallel Huey Tasks Implementation

**Files:**
- Modify: `backend/src/tasks.py`
- Modify: `backend/tests/test_tasks.py`

- [ ] **Step 1: Update tasks.py with 4 functions**
```python
# backend/src/tasks.py
from src.queue import task_queue
from src.metadata import get_exif_data
from src.ai.ocr import extract_text_from_image
from src.ai.clip import ClipTagger
from src.ai.vision import QwenVisionGenerator
from src.config import Settings
from src.database import SessionLocal
from src.db_service import create_photo_record, check_photo_hash_exists
from src.watcher import generate_file_hash

def get_or_create_photo(db, filepath):
    file_hash = generate_file_hash(filepath)
    photo = check_photo_hash_exists(db, file_hash)
    if not photo:
        photo = create_photo_record(db, file_hash, filepath)
    return photo

@task_queue.task()
def metadata_task(filepath: str):
    db = SessionLocal()
    try:
        photo = get_or_create_photo(db, filepath)
        exif = get_exif_data(filepath)
        # photo.exif_data = exif (example update)
        db.commit()
    finally:
        db.close()

@task_queue.task()
def clip_task(filepath: str):
    db = SessionLocal()
    try:
        photo = get_or_create_photo(db, filepath)
        tagger = ClipTagger()
        keywords = tagger.generate_keywords(filepath)
        # photo.keywords = keywords
        db.commit()
    finally:
        db.close()

@task_queue.task()
def vision_task(filepath: str):
    db = SessionLocal()
    try:
        photo = get_or_create_photo(db, filepath)
        gen = QwenVisionGenerator(Settings())
        desc = gen.describe_scene(filepath)
        # photo.description = desc
        db.commit()
    finally:
        db.close()

@task_queue.task()
def ocr_task(filepath: str):
    db = SessionLocal()
    try:
        photo = get_or_create_photo(db, filepath)
        text = extract_text_from_image(filepath)
        # photo.ocr_text = text
        db.commit()
    finally:
        db.close()
```

### Task 2: Dispatching Multi-Parallel Tasks from Observer

**Files:**
- Modify: `backend/src/observer.py`

- [ ] **Step 1: Update Observer dispatch logic**
```python
# backend/src/observer.py
from src.tasks import metadata_task, clip_task, vision_task, ocr_task

# Inside on_created loop
if not photo_exists:
    metadata_task(event.src_path)
    clip_task(event.src_path)
    vision_task(event.src_path)
    ocr_task(event.src_path)
```
