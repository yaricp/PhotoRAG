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
| Restart | Stop PhotoRAG while queued/running photos remain, then relaunch without user resume. | Old work is paused/interrupted and does not start. A selected manual resume uses the bounded queue; a new watched photo can still queue independently. |
| Processing page | Complete more than 50 task records, inspect both tabs, then rerun one photo. | Every photo remains discoverable; each run exposes all applicable phases and old errors; new and old attempts are distinct. |
| Folder/status UI | Add an active watcher; load a legacy watcher without `updated_at`; save vision and translation model configurations after the banner appears. Repeat in English, Russian and Spanish. | No `Invalid Date`; active status has correct meaning; warning refreshes and uses the selected language; configured but unavailable is distinct from unconfigured. |
| Upgrade/installers | Upgrade existing packaged installs and inspect one real runtime per OS, plus all target installer contents. | No model repull, venv reinstall, photo deletion, or silent recovery. Candidate binaries contain the same backend revision and pass packaging checks. |

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
