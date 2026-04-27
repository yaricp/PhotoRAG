# Phase 5.13: Download/Registry Separation & Model Bootstrap Refactor

**Goal:** Cleanly separate two distinct responsibilities that were incorrectly mixed:
1. `download_models_task` — First-install only. Downloads models/vocab to disk. Checks ModelState before acting.
2. `AIModelRegistry` — Runtime singleton. Loads already-downloaded models into RAM once per process. Never touches network.

---

### Architecture Contract

```
download_models_task()              AIModelRegistry
────────────────────────            ────────────────────────────────
Disk/Network concern                RAM concern only
Checks ModelState table             Never checks ModelState
Calls model.download()              Calls model.load() only
Runs ONCE at first install          Runs once per process lifetime
Updates status: downloading/ready   Never downloads, never updates DB
```

---

### Task 1: Fix AIModelRegistry (`registry.py`)
- [x] **Step 1**: Remove `tagger.download()` from `clip_tagger` property — registry only calls `load()`.
- [x] **Step 2**: Update docstring to reflect single responsibility: "RAM concern only. Never downloads."

### Task 2: Refactor `download_models_task` (`tasks.py`)
- [ ] **Step 1**: For each model, check `ModelState` table — if status is already `"ready"`, skip entirely.
- [ ] **Step 2**: Call `model.download()` directly (not through registry) when download is needed.
- [ ] **Step 3**: Update `ModelState` to `"downloading"` → `"ready"` or `"error"` accordingly.
- [ ] **Step 4**: Ensure `data/` directory exists before CLIP vocabulary download.

### Task 3: Fix Relative Path Bug (`clip.py`)
- [ ] **Step 1**: The `data/` prefix was added by the user — verify the `data/` directory is created before download.
- [ ] **Step 2**: Ensure `os.makedirs("data", exist_ok=True)` is called in `download_vocabulary()`.

### Task 4: TDD
- [ ] **Step 1**: Write `test_download_task_skips_if_ready` — verifies that if ModelState is "ready", no download is triggered.
- [ ] **Step 2**: Write `test_download_task_runs_if_pending` — verifies that download() is called when status is not "ready".
- [ ] **Step 3**: Global Green Check (55+ tests passing).

---

### Key Decision
The Registry must **never** call `download()`. If a model is not yet on disk when a task runs (because `download_models_task` hasn't completed yet), the task should fail gracefully and log a clear error — not silently trigger a download in the middle of a Huey worker.
