## Why

A fresh macOS install submitted 23 watched photos in 14 seconds. With `qwen3-vl:2b-instruct` selected for image tasks, Ollama used a 262,144-token context, repeatedly evicted or lost its runner, and most descriptions, tags, and categories failed. PhotoRAG nevertheless logged each pipeline as finished and the Processing page hid older failed tasks. The same shared backend and Ollama workflow ship on Windows, macOS, and Linux, so the next release needs a platform-wide fix rather than a Mac-only workaround.

## What Changes

1. Bound Ollama-backed processing from every entry point and choose a model-aware, resource-aware context for all Ollama models. The user selects the model; PhotoRAG handles context automatically without changing Ollama's global setting or requiring a manual token field.
2. Make pipeline and task outcomes truthful: distinguish completed, completed with errors, skipped due to a missing prerequisite, and interrupted work. Do not declare a photo successfully processed solely because the last phase ran.
3. Show queued/in-progress and completed photo runs separately, with every phase, result, error, and usable retry action. Paginate by photo/run rather than the latest 50 task rows.
4. Preserve interrupted work after a crash or restart and offer an explicit resume action instead of silently reprocessing unfinished photos on application startup.
5. Fix the watched-folder `Invalid Date` display and refresh/localize the pipeline model-warning banner when configuration changes.

## Capabilities

### New Capabilities

- `ollama-inference`: Model capability checks, automatic per-model context selection, bounded requests, and actionable capacity errors across Windows, macOS, and Linux.
- `photo-pipeline`: Shared admission queue, truthful run/task states, completed history, dependency-aware retries, and user-controlled recovery.
- `folder-monitoring`: Reliable watcher status timestamps and meaningful, safe display of missing timestamps.

### Modified Capabilities

- `model-configuration`: The warning banner reflects current effective pipeline configuration, distinguishes unavailable models from missing configuration, and follows the selected language.

## Impact

- Shared Python backend model gateway, observer, folder scan and retry launch paths, pipeline tracker, startup recovery, API schemas, and database migration for persistent run history.
- React Processing, Folders, and model-warning views plus English, Russian, and Spanish strings.
- Focused backend/frontend tests and packaged runtime verification for macOS universal, Windows x64/ARM64, and Linux x64/ARM64. Ollama remains separately installed; existing virtual environments, downloaded models, and photo records must survive an upgrade.
- This change prepares a future implementation. It does not include code edits, a release build, or automatic retries of the current test database.
