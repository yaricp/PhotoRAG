# Cross-platform photo processing stabilization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make multi-photo processing bounded, recoverable, truthful, and visible on every desktop platform.

**Architecture:** The backend stores immutable photo-run and task-attempt history in SQLite and admits all launches through one transactional queue. Ollama inference uses one model-aware context policy and bounded requests. The frontend reads paginated run summaries and shows active/completed work, with localized status data.

**Tech Stack:** Python 3, FastAPI, SQLAlchemy, SQLite, Huey, React, TypeScript, Vitest, pytest, Electron.

## Global Constraints

- Preserve existing photo records, outputs, installed Python environments, and downloaded Ollama models.
- Do not silently reprocess unfinished photos on startup; recovery requires a user action.
- A user chooses an Ollama model, not a manual context token count; custom remote Ollama URLs remain supported.
- Keep all repository notes and instructions in English. Localize product copy in English, Russian, and Spanish.
- Use a real red/green TDD cycle for each behavior; do not change application code before its failing test.
- The authoritative requirements and manual scenarios are in `openspec/changes/stabilize-cross-platform-photo-processing/`.

---

### Task 1: Persistent runs and truthful task outcomes

**Files:** Modify `backend/src/models.py`, `backend/src/db/database.py`, `backend/src/install.py`, `backend/src/pipeline_tracker.py`, `backend/src/incoming_pipeline.py`, and relevant task bodies in `backend/src/tasks/`; test `backend/tests/test_pipeline_tracker.py`, `backend/tests/test_pipeline_retry.py`, and new `backend/tests/test_pipeline_runs.py`.

**Interfaces:** Produce `PipelineRun` with `id`, `photo_id`, `status`, timestamps and attempt-linked `PipelineTask` rows. Produce `create_pipeline_run(photo_id, source)`, `finalize_pipeline_run(run_id)` and `mark_task_skipped(photo_id, phase, task_name, reason)` in `pipeline_tracker.py` for Tasks 2 and 4.

- [ ] Write a test that creates two runs for the same photo and asserts the failed first attempt survives a later successful run, including legacy table migration.
- [ ] Run that test and verify failure from absent run/attempt persistence.
- [ ] Add the additive schema/migration and tracker changes; rerun until green.
- [ ] Write tests where vision fails while independent CLIP succeeds and document embedding has no document; assert dependent work is skipped with a reason and the aggregate is `completed-with-errors`, while legitimate no-op is not reported as generated output.
- [ ] Run red; implement dependency-aware pipeline completion and bounded summary; run green.
- [ ] Write a test that retries a failed description and asserts prior attempt is retained, translation/embedding follow, and CLIP tags are not removed; run red, implement, run green.
- [ ] Run focused existing pipeline tests and commit.

### Task 2: Shared admission queue and explicit recovery

**Files:** Create `backend/src/pipeline_queue.py`; modify `backend/src/main.py`, `backend/src/observer.py`, `backend/src/tasks/folder_scanners.py`, agent-tool rerun entry points, and `backend/src/incoming_pipeline.py`; test new `backend/tests/test_pipeline_queue.py` and existing `backend/tests/test_observer.py`, `backend/tests/test_pipeline_tracker.py`.

**Interfaces:** Consume `PipelineRun`/`create_pipeline_run` from Task 1. Produce `enqueue_photo_run(photo_id, source, folder_scanner_id=None)`, `claim_next_run()`, `resume_run(run_id)`, and queue-position data for Task 4.

- [ ] Write a test that 24 watcher submissions plus concurrent scanner/manual submissions create at most one active run per photo and preserve queue order across separate DB sessions; run red.
- [ ] Implement a SQLite transactional claim and common submission entry point; run green.
- [ ] Write a test that restart marks queued/running work interrupted without deleting task evidence or starting processing; explicit resume enqueues only selected runs; run red, implement, run green.
- [ ] Route each launch path through admission; test one active local Ollama photo-run/inference and continued unrelated native/cloud work.
- [ ] Run focused queue/observer tests and commit.

### Task 3: Model-aware bounded Ollama inference

**Files:** Create `backend/src/ollama_policy.py`; modify `backend/src/model_services.py`, Ollama call sites in `backend/src/ai/`, and configuration/status API in `backend/src/main.py`; test new `backend/tests/test_ollama_policy.py`, existing `backend/tests/test_vision_remote.py`, `backend/tests/test_clip_remote.py`, `backend/tests/test_translation_remote.py`.

**Interfaces:** Produce `resolve_ollama_policy(base_url, model_name, role) -> OllamaPolicy` with `effective_num_ctx`, `reason`, `vision_capable`, and `capacity_known`. All Ollama calls pass the selected `num_ctx`, bounded timeout and local inference gate. Task 4 reads the same policy for a read-only display.

- [ ] Write mocked `/api/show` tests for image capability, 4096 and 262144 limits, missing metadata, shared model across roles, unavailable server, and a custom remote URL; run red.
- [ ] Implement metadata parsing and conservative host/model-aware context policy; run green.
- [ ] Write tests asserting every relevant Ollama request carries the stable `num_ctx` and that timeout, runner death, context overflow, and memory errors propagate as failures; run red, implement, run green.
- [ ] Add read-only policy API/display data and run focused existing inference tests; commit.

### Task 4: Paginated processing history and actions

**Files:** Modify `backend/src/main.py`, `backend/src/schemas.py`, `frontend/src/api/client.ts`, `frontend/src/types/api.ts`, `frontend/src/pages/JobProcessingPage.tsx`, its CSS, and `frontend/src/pages/__tests__/JobProcessingPage.test.tsx`; test new `backend/tests/test_api_pipeline_runs.py`.

**Interfaces:** Consume Tasks 1–3. Expose paginated `/api/pipeline/runs` including status, photo, queue data and output presence, plus `/api/pipeline/runs/{id}/tasks`, selected resume and dependency-aware retry actions.

- [ ] Write an API test with 51 task rows and two runs for a photo; assert both runs paginate and all phases/attempts remain retrievable; run red, implement, run green.
- [ ] Write UI tests for queued/in-progress and completed tabs, queue position/wait, outputs, task errors, retry and full-rerun controls, and 50-row overflow; run red, implement, run green.
- [ ] Add localized English/Russian/Spanish copy and help guidance for the new controls; run type-check/Vitest and commit.

### Task 5: Watcher time and live model warning

**Files:** Modify watcher schema/API in `backend/src/schemas.py` and `backend/src/main.py`, `frontend/src/pages/FoldersPage.tsx`, `frontend/src/components/ui/PipelineWarningBanner.tsx`, i18n JSON files and focused tests.

**Interfaces:** `Watcher.updated_at` is nullable UTC ISO-8601; absent/invalid values render a localized unknown label. The warning re-reads effective model configuration and availability after saves and status changes.

- [ ] Write an API test for a timezone-aware `updated_at` and a frontend test for missing/invalid dates; run red, implement, run green.
- [ ] Write banner tests for model-save refresh, missing configuration versus temporary unavailability, and all three locales; run red, implement, run green.
- [ ] Run focused watcher/banner tests and commit.

### Task 6: Integration and candidates

**Files:** Update `openspec/changes/stabilize-cross-platform-photo-processing/tasks.md` as each task passes; record release evidence under `docs/` only for performed checks.

- [ ] Run backend focused and full pytest, frontend Vitest, lint, type-check, build, and `openspec validate stabilize-cross-platform-photo-processing --strict`.
- [ ] Exercise the 24-photo macOS scenario and inspect actual DB outputs, Ollama runner/context, queue and UI history; record measured results.
- [ ] Exercise available Windows 8 GiB and Linux hosts or record explicitly which hardware checks cannot be run from this environment.
- [ ] Verify model edge cases, existing Ollama pulls/inventory, previous-install upgrade behavior, and user-selected resume.
- [ ] Build macOS universal, Windows x64/ARM64, and Linux x64/ARM64 candidates from one revision where toolchains allow; record versions, checksums, and package smoke-test results.
- [ ] Complete the OpenSpec checkboxes only for verified work, review the diff, and commit.
