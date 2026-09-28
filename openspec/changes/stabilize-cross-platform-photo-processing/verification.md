# Verification plan for the next implementation

This is a future acceptance plan, not a record of completed testing. All result notes and test instructions in this change are in English. No existing PhotoRAG database, Ollama configuration, installed model, or original image should be reset by verification without the tester's explicit choice.

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
