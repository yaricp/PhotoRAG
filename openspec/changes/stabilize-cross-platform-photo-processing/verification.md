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
| Attempt history | Retry one photo until it has both successful and failed historical attempts, then inspect the completed card. | The latest attempt is expanded; older attempts are collapsed but retain their task statuses and individual retry controls. The bulk-retry button's eligibility and behavior are unchanged. |
| Image-quality handling | Process a blurry/low-detail photo, a fully uniform image, and a normal photo through remote CLIP/Ollama. | CLIP sees deterministic blur/detail/uniform signals; labels below 0.5 are discarded; malformed JSON gets one syntax-only repair; a uniform photo has explicit skipped states for every model-driven task while metadata and quality checks still run. |
| Perceptual duplicates | Compare visually similar photos, dissimilar photos with a close dHash, and blank photos, then inspect existing records. | A dHash match is accepted only when aHash or pHash corroborates it; uniform images and stale uncorroborated perceptual rows are omitted; exact file-hash duplicate behavior is unchanged. |
| OCR duration | Run document OCR and a non-OCR vision request through the same Ollama client. | OCR has a 300-second queue and HTTP deadline; other roles retain their existing 120-second deadline and the shared inference gate remains in use. |
| Product version | Open Settings in an installed packaged build. | The displayed version matches Electron's packaged application version. |
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
- At the pre.7 stage, the candidate set had been built and inspected as documented below. Real 24-photo inference and target-OS install/upgrade evidence remained outstanding; task 5.5 was then still open for the candidate build, and the upgrade check was then numbered 5.6 (now 5.7).

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
- At the pre.7 stage, task 5.5 remained open pending candidate builds and real packaged-install smoke tests. Tasks 2.5, 5.2, 5.3, and the then-numbered task 5.6 (now 5.7) remained open pending hardware inference and upgrade runs.

## Cross-platform package candidates — 2026-10-02 (`0.1.5-pre.8`)

All five candidates were built from source revision `0ad7f9a66165df38cb6fffa39930b73aa77a871f` using Electron Builder metadata version `0.1.5-pre.8`; the permanent `frontend/package.json` version remains `0.1.4`. The candidates and `SHA256SUMS` are in the main project at `frontend/dist-electron/ollama-candidate-pre.8/`. Each platform's packaged `app.asar` reports `0.1.5-pre.8`, and each inspected bundle contains `resources/backend/src/main.py`.

| Target | Artifact | Size | SHA-256 | Build/inspection result |
| --- | --- | ---: | --- | --- |
| macOS universal | `PhotoRAG-0.1.5-pre.8-universal.dmg` | 268 MiB | `050277f275335820f12374f9bb80d8f59f52bacf3a8aa57ac167018b9e21984a` | DMG CRC verification passed; bundled Python contains x86-64 and ARM64; `app.asar` version and backend source were verified. No Developer ID signing identity was available; the app was not installed or launched. |
| Windows x64 | `PhotoRAG-Setup-0.1.5-pre.8-x64.exe` | 128 MiB | `5c444c63fa6f7ec787c3963b3cc08163f5c8eae728f3a36ccff968ada1641318` | NSIS build succeeded; Electron and Python executables are PE x86-64; `app.asar` version and backend source were verified. No Windows runtime was available for installation. |
| Windows ARM64 | `PhotoRAG-Setup-0.1.5-pre.8-arm64.exe` | 119 MiB | `24729cd68c49ba725ed6c7873e7c4940f013fb29bf2ff4309b5f9c5dc752d0f3` | NSIS build succeeded; Electron and Python executables are PE AArch64; `app.asar` version and backend source were verified. No Windows ARM64 runtime was available for installation. |
| Linux x64 | `PhotoRAG-0.1.5-pre.8-x86_64.AppImage` | 242 MiB | `0d1c195d2b9429a3ad9f75414d1d7d96bbf773e0af97a4fb06e0a8cc044817c0` | AppImage is ELF x86-64; bundled Python is x86-64; `app.asar` version and backend source were verified. This macOS host cannot execute the AppImage. |
| Linux ARM64 | `PhotoRAG-0.1.5-pre.8-arm64.AppImage` | 213 MiB | `8243076cc04bbe31ee97941647e4816e42a7da2dae16d067633c480725a166e8` | AppImage is ELF AArch64; bundled Python is AArch64; `app.asar` version and backend source were verified. This macOS host cannot execute the AppImage. |

- All five artifact checksums passed `shasum -a 256 -c SHA256SUMS`. Temporary unpacked bundles were removed after inspection. The source tree's Python runtime was restored to the macOS universal 3.13.13 build after cross-platform packaging.
- Linux ARM64 was rerun with an explicit AppImage-only target after electron-builder's default target list also attempted an unavailable Snap build. The delivered ARM64 AppImage passed architecture inspection; no Snap artifact is part of the candidate set.
- After the final UI regression was added, the full frontend suite passed 328 tests in 45 files; `npm run type-check` passed, and ESLint reported 12 warnings with no errors. The focused queue/admission backend group passed 47 tests. Strict OpenSpec validation, `git diff --check`, the five copied artifact checksums, and DMG CRC verification passed.
- OpenSpec task 5.5 is complete. Real packaged installation smoke tests and upgrade preservation checks remain open as tasks 5.6 and 5.7. Tasks 2.5, 5.1, 5.2, and 5.3 also remain open for target-hardware inference, full-suite validation, and cross-OS runtime testing.

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

## Latest pre.8 macOS feedback — 2026-10-03

The user reported repeated failed attempts cluttering completed cards, unreliable CLIP tags/categories, false near-duplicate grouping of photo 36 with photo 32, slow Ollama OCR for documents, missing visible product version, and a bulk-retry action that did not appear eligible after some failures. The user approved the attempt-history, image-quality, OCR, confidence, duplicate, and version changes, and explicitly asked to leave the bulk-retry button's current behavior unchanged while investigating the separate underlying issue.

## Implementation verification — 2026-10-03

- `tests/test_quality_checks.py`, `test_clip_remote.py`, `test_db_service_duplicates.py`, `test_ollama_policy.py`, and `test_incoming_pipeline_blank_image.py` passed together: 112 tests. Coverage includes the 0.5 minimum score, blur/detail prompt signals, one malformed-JSON repair, exact-uniform detection, explicit skips for all pipeline model tasks, dHash corroboration, blank-image exclusion, and hiding stale perceptual records without valid hashes.
- `tests/test_pipeline_runs.py` passed 30 tests after its temporary-database fixture was taught to bypass the image gate, which is covered separately by the blank-image pipeline tests. `tests/test_model_services.py` passed 18 tests.
- The full frontend suite passed 332 tests in 45 files; `npm run type-check` passed. ESLint reported 12 warnings and no errors. Ruff checks on changed Python files, `git diff --check`, and `openspec validate stabilize-cross-platform-photo-processing --strict` passed.
- A combined backend invocation that included legacy mocking-heavy suites was not green: it exposed module-level `MagicMock` contamination between test modules and outdated `test_pipeline_perceptual.py` expectations (it calls the async task with an obsolete second argument and expects the removed `folder_scanners.start_pipeline` entry point). The new duplicate-policy and model-gate suites pass in isolation. The broader backend suite and real Ollama/platform acceptance remain open; no packaged pre.9 build or hardware inference is claimed here.
