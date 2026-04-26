# Phase 5.3: Atomic ID-based Parallel Ingestion

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ensure the Photo record is created synchronously in the observer to prevent race conditions. All background tasks will receive a `photo_id` and update an existing row.

---

### Task 1: Updating the Observer Logic (Synchronous)

**Files:**
- Modify: `backend/src/observer.py`
- Modify: `backend/tests/test_observer.py`

- [ ] **Step 1: Update Observer to Create Record and yield ID**
- [ ] **Step 2: Update task dispatching calls to use `photo_id`**

### Task 2: Updating Huey Tasks (ID-linkage)

**Files:**
- Modify: `backend/src/tasks.py`
- Modify: `backend/tests/test_tasks_parallel.py`

- [ ] **Step 1: Update task signatures to `(photo_id: int)`**
- [ ] **Step 2: Each task fetches `photo.file_path` from DB before AI processing**

### Task 3: TDD Verification
- [ ] **Step 1: Update `test_tasks_parallel.py` with the new ID logic**
- [ ] **Step 2: Run and reach Green**
