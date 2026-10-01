## Why

A fresh macOS install submitted 23 watched photos in 14 seconds. With `qwen3-vl:2b-instruct` selected for image tasks, Ollama used a 262,144-token context, repeatedly evicted or lost its runner, and most descriptions, tags, and categories failed. PhotoRAG nevertheless logged each pipeline as finished and the Processing page hid older failed tasks. The same shared backend and Ollama workflow ship on Windows, macOS, and Linux, so the next release needs a platform-wide fix rather than a Mac-only workaround.

Testing the `0.1.5-pre.6` macOS candidate exposed additional Processing-page issues and a retry failure: tag inference returned successfully for photos 7 and 8, but saving failed when repeated tag labels violated the unique `(photo_id, tag_id)` constraint. One later retry for photo 7 timed out; a later retry for photo 8 saved 29 tags. The UI also needs to distinguish unique photos from attempts and keep an active retry visually separate from old results.

## What Changes

1. Bound Ollama-backed processing from every entry point and choose a model-aware, resource-aware context for all Ollama models. The user selects the model; PhotoRAG handles context automatically without changing Ollama's global setting or requiring a manual token field.
2. Make pipeline and task outcomes truthful: distinguish completed, completed with errors, skipped due to a missing prerequisite, and interrupted work. Do not declare a photo successfully processed solely because the last phase ran.
3. Show queued/in-progress and completed photos separately, with every phase, result, error, and usable retry action. Group attempts per photo and paginate photo entries rather than the latest 50 task rows.
4. Preserve interrupted work after a crash or restart. Add an opt-in startup retry setting, off by default, for interrupted and failed tasks; preserve completed outputs and respect explicit pause/cancel actions.
5. Fix the watched-folder `Invalid Date` display and refresh/localize the pipeline model-warning banner when configuration changes.
6. Refine Processing-page navigation and photo cards: show counts on both tabs, put currently running photos before queued photos, collapse completed outputs while keeping phase statuses visible, hide old outputs on an active retry, and group attempts under one photo entry.
7. Make tag persistence safe for duplicate model labels and repeated attempts so valid inference results do not fail as a whole on a uniqueness conflict.
8. Add a one-click Processing action to enqueue all eligible failed and incomplete tasks through the same bounded queue.

## Capabilities

### New Capabilities

- `ollama-inference`: Model capability checks, automatic per-model context selection, bounded requests, and actionable capacity errors across Windows, macOS, and Linux.
- `photo-pipeline`: Shared admission queue, truthful run/task states, completed history, dependency-aware retries, opt-in startup recovery, and user-controlled bulk retry.
- `folder-monitoring`: Reliable watcher status timestamps and meaningful, safe display of missing timestamps.

### Modified Capabilities

- `model-configuration`: The warning banner reflects current effective pipeline configuration, distinguishes unavailable models from missing configuration, and follows the selected language.

## Impact

- Shared Python backend model gateway, observer, folder scan and retry launch paths, pipeline tracker, startup recovery preference, idempotent tag persistence, API schemas, and database migration for persistent run history.
- React Processing, Folders, and model-warning views, a Processing recovery preference and bulk retry control, plus English, Russian, and Spanish strings.
- Focused backend/frontend tests and packaged runtime verification for macOS universal, Windows x64/ARM64, and Linux x64/ARM64. Ollama remains separately installed; existing virtual environments, downloaded models, and photo records must survive an upgrade.
- This change prepares a future implementation. It does not include code edits, a release build, or automatic retries of the current test database.
