## Context

Ollama runs outside PhotoRAG and exposes a local HTTP API. PhotoRAG already stores Ollama as `mode=remote, model_provider=ollama` and uses `langchain-ollama` for inference. The first-run wizard runs before the Python backend starts, so downloads must be orchestrated by Electron. The existing local-model download step supplies the progress UI.

## Goals / Non-Goals

**Goals:** Explicit user choice of models; automatic download with visible progress on Windows, macOS and Linux; a localized setup explanation; installed-model and disk management; no command-line requirement for ordinary use.

**Non-Goals:** Bundling or installing Ollama; automatically choosing or deleting models; managing a remote Ollama host's filesystem; guaranteeing a model's quality on every PhotoRAG task.

## Decisions

1. **Use Ollama's local HTTP API for downloads and deletion.** `POST /api/pull` streams per-layer progress; `GET /api/tags` reports installed models and sizes; `DELETE /api/delete` removes a named model. These endpoints are available across supported desktop platforms, whereas invoking a CLI from a packaged app depends on platform-specific executable paths and PATH propagation. PhotoRAG can attempt to start an installed `ollama serve` when localhost is unavailable. Command-line instructions remain optional in help.
2. **Keep the persisted two-mode schema.** The new third UI choice maps to the existing `remote`/`ollama` values so model inference needs no migration. Changing processing choice clears stale cloud credentials and model names. The user must select or type the Ollama model; the first suggestion is never silently selected.
3. **Pull only after an explicit configuration action.** Continuing the wizard or saving a task configuration pulls the chosen model if absent, reports progress and errors, and applies the task configuration only after a successful pull on the Models page. Duplicate requests for the same model are collapsed. On the Models page, progress is inline and does not block other model cards; an already installed model is saved without another pull. Other applications' Ollama models remain visible and usable.
4. **Constrain automated management to localhost.** A custom Ollama URL may still be used for inference. Local download and storage management do not assume the remote machine's disk is available to PhotoRAG. The UI must explain this limitation rather than silently fail or misreport space.
5. **Measure the model disk conservatively.** The inventory comes from Ollama's tags API. The model directory is inferred from an installed model's `show` metadata when possible, otherwise from `OLLAMA_MODELS` or documented platform defaults. Disk free space is shown only if the directory can be found; an unverified directory is labeled as an estimate. Listed model sizes can include shared blobs, so they are not exact reclaimable bytes. Warn at less than 5 GiB free or less than 10% of the volume.
6. **Share help content.** The modal renders the existing translated Ollama article without application or help navigation. Its recommendation table maps all six model capabilities to example model tags, while a separate optional section documents CLI use. External Ollama links open in the system browser.
7. **Respect embedding dimensions and query instructions.** The `mxbai-embed-large` suggestion produces 1024-dimensional vectors and recommends a retrieval prefix for queries. Update the existing backend dimension map and prefix handling so experimentation does not create a mismatched vector table.
8. **Report remote classification failures accurately.** A vision model with a small context window may reject a large CLIP candidate list. Retry with smaller groups until it fits; if the provider still fails or returns malformed JSON, propagate the error so the task is not shown as completed.

## Risks / Trade-offs

- **Ollama not installed or not running** → Show an actionable retryable error and retain the selected configuration; never claim a model is ready before pull success.
- **Model folder moved by the Ollama service** → Prefer a path returned by Ollama metadata; if it cannot be verified, mark the disk estimate or show free space as unknown.
- **Shared models or active task dependencies** → Require confirmation before single/all deletion and identify models selected in PhotoRAG. Never delete automatically.
- **Old Ollama version or insufficient hardware** → State Qwen3-VL's minimum Ollama version and present model suggestions as starting points, with editable names.

## Migration Plan

No database migration is needed. Existing `remote`/`ollama` configurations appear as the new third processing choice. Users can keep existing Ollama models; the downloader checks `/api/tags` before pulling. Reverting the UI leaves stored configurations and downloaded Ollama models intact.

## Open Questions

None required for this change. Exact model quality remains a release-validation task using representative photos and hardware.

## Verification limits

The automated tests mock Ollama's HTTP responses and Electron IPC. They verify pull progress, reuse, cancellation, deletion, configuration and localized UI behavior, but they do not install or run Ollama on Windows, macOS or Linux. Before release, the packaged builds should be checked against an installed Ollama app on each platform, including a custom `OLLAMA_MODELS` location and low disk space.

Candidate installers use an Electron Builder metadata version override and a separate output directory. This keeps the published-version files synchronized with the last release while avoiding replacement of earlier installers. Candidate packaging and runtime checks are tracked in section 5 of `tasks.md`.

The local packaging environment has Electron 43.2.0 platform archives cached but cannot reach GitHub for a fresh checksum manifest. Offline candidate builds may use those previously cached archives with the download-time checksum request disabled; they are for local verification only and must be rebuilt in CI with normal checksum validation before publication.
