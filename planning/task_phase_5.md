# Phase 5: Backend Operations & Process Wiring

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Connect the AI components into the SQLite-backed Huey queue and implement the real-time directory observer Using `watchdog`.

**Architecture:** We will define `tasks.py` to handle the asynchronous execution of our LangGraph. We will build an `ObserverManager` that runs the `watchdog` library in a background thread/process, ensuring every new file is instantly hashed (Tier 1) and queued for AI (Tier 2).

**Tech Stack:** Python 3, Huey, Watchdog, SQLAlchemy, Pytest.

---

### Task 1: Huey Background Task Definitions

**Files:**
- Create: `backend/src/tasks.py`
- Create: `backend/tests/test_tasks.py`

- [ ] **Step 1: Write test for task registration**
```python
# backend/tests/test_tasks.py
from src.tasks import process_photo_task
from src.queue import task_queue

def test_task_is_registered():
    assert 'process_photo_task' in task_queue._registry
```
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement Task Logic**
```python
# backend/src/tasks.py
from src.queue import task_queue
from src.graphs.ingestion import ingest_workflow

@task_queue.task()
def process_photo_task(filepath: str):
    # This runs in the background Huey process
    result = ingest_workflow.invoke({"filepath": filepath})
    return result
```
- [ ] **Step 4: Run test to pass**
- [ ] **Step 5: Commit**

### Task 2: Directory Watcher (Watchdog)

**Files:**
- Create: `backend/src/observer.py`
- Create: `backend/tests/test_observer.py`

- [ ] **Step 1: Write test for Watcher event handling**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement Watchdog Event Handler**
```python
# backend/src/observer.py
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from src.watcher import generate_file_hash
from src.tasks import process_photo_task

class PhotoEventHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory and event.src_path.lower().endswith(('.jpg', '.png', '.jpeg')):
            # Tier 1: Immediate Hashing
            file_hash = generate_file_hash(event.src_path)
            # Tier 2: Queue for AI
            process_photo_task(event.src_path)

def start_observer(path: str):
    observer = Observer()
    observer.schedule(PhotoEventHandler(), path, recursive=False)
    observer.start()
    return observer
```
- [ ] **Step 4: Run test to pass**
- [ ] **Step 5: Commit**

### Task 3: API Lifecycle Integration

**Files:**
- Modify: `backend/src/main.py`
- Modify: `backend/tests/test_main.py`

- [ ] **Step 1: Write test for /watch starting the observer**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement Lifecycle logic in FastAPI**
```python
# backend/src/main.py
from src.observer import start_observer
# Store active observers in a global dict
active_observers = {}
```
- [ ] **Step 4: Run test to pass**
- [ ] **Step 5: Commit**
