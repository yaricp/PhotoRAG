# Phase 5.1: Refined Ingestion Pipeline

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the strict synchronous/asynchronous split. The observer will perform fast checks (Ext, Hash, DB Check) and the background LangGraph will handle EXIF, CLIP, OCR, and Vision enrichment.

---

### Task 1: EXIF Metadata Extraction

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/src/metadata.py`
- Create: `backend/tests/test_metadata.py`

- [ ] **Step 1: Write test for EXIF extraction**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement Metadata logic**
```bash
# Add to requirements.txt: exifread
```
```python
# backend/src/metadata.py
import exifread

def get_exif_data(filepath: str) -> dict:
    with open(filepath, 'rb') as f:
        tags = exifread.process_file(f, details=False)
        return {
            "model": str(tags.get('Image Model', 'Unknown')),
            "datetime": str(tags.get('Image DateTime', 'Unknown')),
            "gps_lat": tags.get('GPS GPSLatitude'),
            "gps_lon": tags.get('GPS GPSLongitude')
        }
```
- [ ] **Step 4: Run test to pass**

### Task 2: Synchronous Observer Filtering

**Files:**
- Modify: `backend/src/observer.py`
- Modify: `backend/tests/test_observer.py`

- [ ] **Step 1: Update Test to mock DB check**
- [ ] **Step 2: Implement Sync Filtering in Observer**
    - [x] Extension check
    - [x] Generate hash
    - [ ] DB check (`db.query(Photo).filter_by(hash=hash).first()`)
    - [ ] Dispatch to Huey if new.

### Task 3: Background Pipeline Refactor (LangGraph)

**Files:**
- Modify: `backend/src/graphs/ingestion.py`
- Modify: `backend/src/tasks.py`

- [ ] **Step 1: Update IngestionState to include all metadata fields**
- [ ] **Step 2: Add nodes for Metadata, OCR, CLIP, and Vision**
- [ ] **Step 3: Ensure each node updates the DB state for the photo record**
