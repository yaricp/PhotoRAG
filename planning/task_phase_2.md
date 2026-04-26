# Phase 2: Backend Foundations (Database, Queue, API)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Establish the SQLAlchemy connections, the SQLite Huey background processing queue, and the FastAPI application containing our Watcher/SSE endpoints.

**Architecture:** We bridge the previously defined schemas to a real database engine. We initialize `SqliteHuey` to safely queue our asynchronous ML tasks. We launch the `main.py` FastAPI app providing standard REST routing alongside Server-Sent Events via native Generators.

**Tech Stack:** Python 3, FastAPI, SQLAlchemy, Huey, pytest.

---

### Task 1: Database Connections & Engine

**Files:**
- Create: `backend/src/database.py`
- Modify: `backend/tests/test_models.py`

- [ ] **Step 1: Write failing connection test**
```python
# backend/tests/test_models.py (append)
from src.database import get_db

def test_db_session_yields():
    generator = get_db()
    session = next(generator)
    assert session is not None
```
- [ ] **Step 2: Run test to verify it fails** (missing `database.py`)
- [ ] **Step 3: Implement Database logic**
```python
# backend/src/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.config import Settings

settings = Settings()
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```
- [ ] **Step 4: Run test to pass**
- [ ] **Step 5: Commit**

### Task 2: SQLite Task Queue (Huey)

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/src/queue.py`
- Test: `backend/tests/test_queue.py`

- [ ] **Step 1: Write failing Queue instantiation test**
```python
# backend/tests/test_queue.py
import os
from src.queue import task_queue

def test_huey_is_configured_with_sqlite():
    assert task_queue.name == 'photo_processor_queue'
```
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Add dependencies and implement queue**
```bash
# Add to requirements.txt: huey==2.5.0
```
```python
# backend/src/queue.py
from huey import SqliteHuey

# A lightweight SQLite-backed queue for safely dispatching heavy ML inferences
task_queue = SqliteHuey(name='photo_processor_queue', filename='tasks.sqlite3')
```
- [ ] **Step 4: Run test to pass**
- [ ] **Step 5: Commit**

### Task 3: FastAPI Application & Endpoints

**Files:**
- Create: `backend/src/main.py`
- Test: `backend/tests/test_main.py`

- [ ] **Step 1: Write API tests for /watch and /stream endpoints**
```python
# backend/tests/test_main.py
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_watch_endpoint():
    response = client.post("/api/watch", json={"path": "/mock/path"})
    assert response.status_code == 200
    assert response.json()["status"] == "watching"
```
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement Main application logic**
```python
# backend/src/main.py
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Photo Describer MVP")

class WatchRequest(BaseModel):
    path: str

@app.post("/api/watch")
def trigger_directory_watch(request: WatchRequest):
    # Triggers Tier 1 watchdog
    return {"status": "watching", "target": request.path}

@app.get("/api/stream")
def sse_event_stream():
    # Will yield Async generator for SSE UI updates
    return {"status": "stream_placeholder"}
```
- [ ] **Step 4: Run test to pass**
- [ ] **Step 5: Commit**
