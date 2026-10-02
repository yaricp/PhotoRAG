# Verification plan for the next implementation

The acceptance checks below remain the future manual/platform acceptance plan. The execution notes at the end record automated evidence only. All result notes and test instructions in this change are in English. No existing PhotoRAG database, Ollama configuration, installed model, or original image should be reset by verification without the tester's explicit choice.

## Baseline to reproduce

- On the 16 GiB macOS test machine, Ollama held `context_length=262144` while its own hardware default log was 4096. The observed Qwen3-VL image requests used approximately 4,044–8,408 input tokens. Ollama predicted 29.8 GiB for the 262,144-token load and repeatedly lost/reloaded its runner.
- A watcher submitted 23 photos within 14 seconds; phase-1 description/tag/category failures were recorded, while the pipeline emitted `FINISHED` and the page showed only 50 recent task rows.
- An active watcher displayed `Invalid Date` because the API schema omitted `updated_at`; the model warning used a one-time configuration snapshot.

## Acceptance checks

| Area | Procedure | Required evidence |
| --- | --- | --- |
| Automatic context | Keep Ollama's global 262,144-token setting, select `qwen3-vl:2b-instruct` for image roles, process representative normal and high-resolution photos. Repeat with another vision model and a model with a smaller native limit. | PhotoRAG sends an explicit bounded effective context within the selected model's limit; the global Ollama setting is unchanged; the UI shows the chosen value; oversized inputs produce a bounded, clear outcome. No Qwen-name-only branch. |
| Image compatibility | Select a text-only Ollama model for description/OCR/tagging. | The mismatch is visible before successful image processing is claimed; no fake description, tags, or categories are saved. |
| Bulk import | Add 24 photos to a watched folder in one burst on the macOS host, including ordinary and high-resolution images. | All 24 have visible queued/running/completed or completed-with-errors run records; concurrency stays within the policy; successful outputs exist in the database; any failures have task-level reasons and are not hidden behind green phase-4 rows. |
| Limited Windows hardware | Repeat with the 8 GiB Windows test machine and the model chosen by the tester. | Work stays bounded. If the model cannot fit, tasks finish with actionable resource errors and remain retryable; the application does not hang indefinitely or claim success. |
| Linux | Repeat normal import and one induced Ollama failure on a real Linux install. | The same context, queue, status, and retry contract holds without OS-specific code paths. |
| Retry dependencies | Cause description to fail, then retry only that task after Ollama recovers. | Description, dependent translation/embedding, independent tags/categories, and prior attempt history have correct outcomes; no successful independent data disappears. |
| Startup retry | Stop PhotoRAG with queued/running work and leave failed tasks, then relaunch with the setting off and again with it on. | Off leaves old work visible and idle. On enqueues at most one attempt per eligible failed/interrupted task through the bounded queue; successful, explicitly paused, canceled, and already active work is not replayed; a second failure does not loop during that session. |
| Bulk retry | Make several photos contain failed/interrupted tasks and click `Restart all failed and unfinished tasks`. | Every eligible task is enqueued once through the shared queue; completed outputs and attempt history remain; active work is not duplicated; queue progress and attempt counts update. |
| Processing page | Complete more than 50 task records, inspect both tabs, then retry one photo several times. | Both tab counts remain visible and count distinct photos; a photo has one card and shows its attempt count; active photos sort before queued photos; completed outputs are collapsed while phase statuses remain visible; an active retry does not show previous outputs as current results. |
| Duplicate tag output | Use or mock an Ollama tag response containing repeated normalized labels, then retry after some tags are already attached. | Each distinct tag association is saved once with deterministic confidence handling; valid results are not lost to a unique-constraint failure; retry history remains inspectable. |
| Folder/status UI | Add an active watcher; load a legacy watcher without `updated_at`; save vision and translation model configurations after the banner appears. Repeat in English, Russian and Spanish. | No `Invalid Date`; active status has correct meaning; warning refreshes and uses the selected language; configured but unavailable is distinct from unconfigured. |
| Upgrade/installers | Upgrade existing packaged installs and inspect one real runtime per OS, plus all target installer contents. | No model repull, venv reinstall, or photo deletion. A missing retry preference defaults off; an existing preference survives the upgrade. Candidate binaries contain the same backend revision and pass packaging checks. |

## Evidence to capture

- Source revision, installer version and checksum, OS/architecture, RAM/GPU class, Ollama version, model names and their reported maximum contexts.
- For each scenario: run/task counts by status, per-photo presence of description/tags/categories, queue peak, effective `num_ctx`, request duration, timeout/runner errors, and Ollama's loaded-model/runner state. Never attach original photos or API credentials to the result notes.
- Automated test output and any platform limitation. A package build without real Ollama execution is recorded as packaging verification, not runtime acceptance.

## Automated execution notes — 2026-10-01

- Context policy tests cover 4,096-token native models, a 262,144-token native/global default, unknown metadata, text-only models selected for image roles, remote hosts, shared roles, and role/host budgets. The global `OLLAMA_CONTEXT_LENGTH=262144` environment value remains unchanged while PhotoRAG sends its explicit 16,384-token policy for the mocked 16 GiB vision host.
- Request tests verify thread/process serialization, bounded request deadlines, propagated timeout/runner/memory/context failures, rejection of empty generations and truncated-context results, exact inline base64 image transfer, and a clear error for unsupported image blocks.
- The current macOS environment reports 16.0 GiB physical RAM. The Ollama executable is installed, but the sandbox could not access its localhost API (`ollama list` was denied at the local socket); no installed model or real inference was verified. No hardware calibration is claimed, and OpenSpec task 2.5 remains open until target-machine runs are recorded.
- The Ollama policy suite now passes 51 tests, including a regression that verifies a custom Ollama URL is used for both model metadata lookup and chat inference. OpenSpec task 5.4 is complete.
- The focused backend run/retry, queue/admission/watcher, inference-provider, and model-service groups passed in isolated runs (189 tests before the custom-URL test was added). A later full `pytest -q --tb=short` invocation stalled and was interrupted after 40.54 seconds; its summary was 261 passed, 6 failed, and 4 errors. Four SQLite vector fixtures report `no such module: vec0`; route and queue tests also receive `MagicMock` modules instead of the real dependencies. A reduced run of `test_api_duplicates.py` followed by the watcher route test reproduces order sensitivity: the legacy test leaves `langgraph` as a non-package mock, so `src.main` cannot import `langgraph.checkpoint.memory`. The focused route/queue suites pass in isolation, but the full backend suite is not green; task 5.1 remains open.
- Repeating the full backend command on 2026-10-01 produced the same order-sensitive result and stalled after 92.93 seconds: 261 passed, 6 failed, and 4 errors before interruption. Running `tests/test_pipeline_admission_routes.py` by itself passed all 16 tests (including all `vec0` fixtures), and `tests/test_pipeline_queue.py` passed all 22 tests. This confirms the affected feature groups pass in isolation; the combined collection still leaks module-level dependency mocks. Task 5.1 remains open.
- `/opt/anaconda3/bin/ruff check .` passed. `ruff format --check .` reported 10 files requiring formatting, including broad pre-existing files; no repository-wide reformat was applied. Frontend validation passed with 45 Vitest files / 320 tests, `npm run type-check`, ESLint with 12 warnings and no errors, and `npm run build`.
- `openspec validate stabilize-cross-platform-photo-processing --strict` passed. The sandbox also denied access to Ollama at `127.0.0.1:11434`.

## Latest packaged-Mac test feedback — 2026-10-02

The installed `0.1.5-pre.6` run log (`photorag.log`, last modified 2026-10-02 00:11 local time) shows that the reported tag retries had more than one outcome:

- For photo 7, the initial tag attempt and a retry both reached Ollama with `qwen3-vl:2b-instruct` and a 16,384-token effective context, but phase 1 failed while saving with `UNIQUE constraint failed: photo_tags.photo_id, photo_tags.tag_id`. A later retry ended with `TimeoutError: Ollama request deadline exceeded` after about 115 seconds. No successful tag-save event for photo 7 appears later in this log.
- For photo 8, the initial attempt and its first retry failed on the same `photo_tags` unique constraint. A subsequent retry saved 29 tags successfully.
- The log records successful Ollama call results before the unique-constraint errors. This points to duplicate tag labels or a repeated photo/tag association in persistence, rather than a model that never received or answered the request. The timeout for photo 7 is a separate failure mode and still needs to remain visible and retryable.
- These are log-based findings, not a claim that every retry failed: photo 8 eventually succeeded. New regression tests cover duplicate labels within one response, prior photo/tag associations, and concurrent same-photo writes. No image contents or credentials are included here.

The requested Processing refinements are now part of the acceptance scope: stable counts on both tabs, one photo card with an attempt count, active-before-queued sorting, collapsed completed outputs with phase markers still visible, and no previous outputs shown as current while a retry is active. Startup recovery is opt-in: the setting defaults off, and both startup retry and the one-click bulk action use the shared bounded queue.

## Implementation verification — 2026-10-02

- The focused backend recovery/history/tag command passed 84 tests across `test_pipeline_queue.py`, `test_pipeline_admission_routes.py`, `test_pipeline_runs.py`, `test_pipeline_retry.py`, `test_clip_tag_persistence.py`, and `test_tag_confidence.py`. It includes the 24-photo bulk-recovery case and verifies that duplicate normalized labels no longer lose an otherwise valid CLIP result.
- The focused Ollama policy/model-service command passed 69 tests across `test_ollama_policy.py` and `test_model_services.py`.
- The full frontend suite passed 325 tests in 45 files. `npm run type-check` passed. ESLint reported 12 existing warnings in unrelated files and no errors. The Processing/Folders/pipeline-warning subset passed 20 tests.
- `openspec validate stabilize-cross-platform-photo-processing --strict` and `git diff --check` passed.
- A full backend `pytest -q` run was interrupted after about 174 seconds: 262 passed, 15 failed, and 4 errored before interruption. The vector-table fixtures report `no such module: vec0`; the combined suite also leaks `MagicMock` modules into route/queue tests. The focused affected suites pass in isolation, so task 5.1 remains open until the project-wide test-order/environment failures are resolved.
- A fresh `pytest -q --maxfail=1 --tb=short` run reproduced collection-order contamination at `test_clip_tag_persistence`: after collection, `src.tasks` and `src.tasks.clip_tasks` are `MagicMock` entries installed by legacy test modules at import time, so the persistence test never calls the real saver. The API duplicate/garbage/history/settings suites now scope their optional-module stubs to fixtures; their combined 24-test group passes with the pipeline regressions. Other legacy module-level stubs still leave the whole backend suite non-green, so task 5.1 remains open.
- The combined focused backend recovery/history/tag and API run passed 106 tests. It exercises the Mac feedback fixes together with the previously passing queue, retry, and persistence coverage.
- The `0.1.5-pre.7` candidate set has now been built and inspected as documented below. Real 24-photo inference and target-OS install/upgrade evidence remain outstanding; tasks 2.5, 5.1, 5.2, 5.3, 5.5, and 5.6 remain open.

## Additional bulk-retry visibility evidence — 2026-10-02

- The installed pre.7 app logged `POST /api/pipeline/retry-eligible` as HTTP 202 at `06:36:35.152Z`, followed by an active-list HTTP 200 at `06:36:35.162Z` and repeated active-list polls while the batch ran. Access logs do not retain response bodies, so they cannot establish which run cards reached React.
- Database runs 36–48 covered 13 photos. Twelve ran only `embedding_document_text_task` and completed as `skipped: Not a document` within milliseconds. Photo 7's run 42 executed CLIP successfully and stayed active for about 48 seconds; all 13 runs were settled by `06:37:26Z`. This supports the false-eligibility diagnosis, while the user's report that no card appeared remains a distinct UI observation.
- Added a Processing regression test with an older empty active-list request completing after the bulk refresh has rendered a queued photo. The test failed before the request-order guard and passed after it.

## Cross-platform package candidates — 2026-10-02 (`0.1.5-pre.7`)

All five artifacts were built from source revision `9a92bb2` with Electron Builder's metadata version override. The permanent `frontend/package.json` version remains `0.1.4`. Artifacts and `SHA256SUMS` are in `frontend/dist-electron/ollama-candidate-pre.7/` in the active worktree. Each packaged `app.asar` reports `0.1.5-pre.7`, and each unpacked target contained `resources/backend/src/main.py`.

| Target | Artifact | Size | SHA-256 | Build/inspection result |
| --- | --- | ---: | --- | --- |
| macOS universal | `PhotoRAG-0.1.5-pre.7-universal.dmg` | 268 MiB | `d09b470c1fb23b9dcb60d4e14b308611c0fc4c1ed887f1dc3b11884fb08ae7cc` | DMG built; bundled Python is universal x86-64/ARM64; backend present; `app.asar` version verified. No Developer ID identity was available, and the app was not installed or launched. |
| Windows x64 | `PhotoRAG-Setup-0.1.5-pre.7-x64.exe` | 128 MiB | `21b7d610b12e7285b891b4675073d4da2e7a4f705174475aca7d6249518b1970` | NSIS build succeeded; unpacked Electron and Python are x86-64; backend present; `app.asar` version verified. No Windows runtime was available for installation. |
| Windows ARM64 | `PhotoRAG-Setup-0.1.5-pre.7-arm64.exe` | 119 MiB | `0fb6cee7d258a3ff1436f02476eee8979b0075b4ce5da89a4203d40b5c8dbb52` | NSIS build succeeded; unpacked Electron and Python are AArch64; backend present; `app.asar` version verified. No Windows ARM64 runtime was available for installation. |
| Linux x64 | `PhotoRAG-0.1.5-pre.7-x86_64.AppImage` | 242 MiB | `c572bb743065fac423131a007efa0dfe1f728498a80d2fdcddde76c476f7af7e` | AppImage ELF and bundled Python are x86-64; backend present; `app.asar` version verified. This macOS host cannot execute the AppImage. |
| Linux ARM64 | `PhotoRAG-0.1.5-pre.7-arm64.AppImage` | 213 MiB | `440d487e71d0d6a81bfcc6f98b3f79d46eb4a6b846368004bd871865ab63a3c6` | AppImage ELF and bundled Python are AArch64; backend present; `app.asar` version verified. This macOS host cannot execute the AppImage. |

- All five artifact checksums passed `shasum -a 256 -c SHA256SUMS`. Temporary unpacked directories were removed after architecture and bundle inspection; installable artifacts, blockmaps, build metadata, and the checksum list remain.
- OpenSpec task 5.5 remains open pending real packaged-install smoke tests. Tasks 2.5, 5.2, 5.3, and 5.6 remain open pending hardware inference and upgrade evidence.

## Cross-platform package candidates — 2026-10-01

All five artifacts below were built from application source revision `7f9775a` with Electron Builder's metadata version override `0.1.5-pre.6`. The permanent `frontend/package.json` version remains `0.1.4`, matching the pre.5 test-build convention. Artifacts are in `frontend/dist-electron/ollama-candidate-pre.6/` in the main workspace. These are test candidates, not a release: no real target-OS install/upgrade or Ollama inference was run.

| Target | Artifact | Size | SHA-256 | Build/inspection result |
| --- | --- | ---: | --- | --- |
| macOS universal | `PhotoRAG-0.1.5-pre.6-universal.dmg` | 268 MiB | `3b6a2b7d70ca2d350905f377612fb6bd294808a62800987d96ce93c838699d4e` | Build succeeded; DMG checksum valid; bundle structure passed 9/9 assertions, including universal Python 3.13.13 and backend files; `app.asar` reports `0.1.5-pre.6`. No Developer ID signing identity was available; real install/launch not verified. |
| Windows x64 | `PhotoRAG-Setup-0.1.5-pre.6-x64.exe` | 128 MiB | `f578839b101ea56b1b35d6a186979b4430129e47be9fd97259ef2529c39996f2` | NSIS build succeeded; unpacked app and Python are x86-64, backend is present, and `app.asar` reports `0.1.5-pre.6`. Real Windows install/launch not verified. |
| Windows ARM64 | `PhotoRAG-Setup-0.1.5-pre.6-arm64.exe` | 119 MiB | `8d6467a0051ec91169ae4148fcffa6d10108b5c88734185ce2d4684e7f51dd34` | NSIS build succeeded; unpacked app and Python are AArch64, backend is present, and `app.asar` reports `0.1.5-pre.6`. Real Windows install/launch not verified. |
| Linux x64 | `PhotoRAG-0.1.5-pre.6-x86_64.AppImage` | 242 MiB | `a4b999f5ba9c94003fc925bdbb85c8b4bac74d96684abb743ae62af088fd70a6` | AppImage build succeeded; outer ELF and bundled Python are x86-64, backend is present, and `app.asar` reports `0.1.5-pre.6`. This macOS host cannot execute the AppImage. |
| Linux ARM64 | `PhotoRAG-0.1.5-pre.6-arm64.AppImage` | 213 MiB | `8b7309237b32b0b3e7ed33ef8b2cba36083c8fcaa8cad59b0ace5c6c4d755411` | Explicit AppImage-only target succeeded; outer ELF and bundled Python are AArch64, backend is present, and `app.asar` reports `0.1.5-pre.6`. This macOS host cannot execute the AppImage. |

- All five candidates passed `shasum -a 256 -c SHA256SUMS`. The temporary unpacked directories were removed after inspecting their backend, frontend archive version, and target Python architecture; the installable artifacts and checksum file remain.
- OpenSpec task 5.5 remains open because real packaged-install smoke tests are pending. Tasks 2.5, 5.2, 5.3, and 5.6 also remain open pending target-hardware and upgrade runs.
