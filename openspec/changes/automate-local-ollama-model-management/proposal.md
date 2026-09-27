## Why

PhotoRAG currently treats Ollama as a remote provider in model setup and asks users to manage its models in a terminal. The first-run help link also leaves the wizard, and Windows messaging says local models are unavailable even though separately installed Ollama works. Users need one local-model workflow that works in Windows, macOS and Linux and lets them manage disk usage as they experiment.

## What Changes

- Add “Local via Ollama” as a third visible processing choice while retaining the existing HTTP-backed `remote`/`ollama` configuration internally.
- Let users explicitly choose a model for each task, then download it through Ollama in the background with progress during setup or when saving a model configuration. Reuse an already installed model.
- Provide a dedicated Ollama model page showing installed names, sizes, the model disk’s free space where determinable, and a low-space warning. Add user-initiated single-model and all-model deletion with confirmation, including a warning for models used by PhotoRAG.
- Open the localized Ollama help article in a closable modal from setup and model configuration. Show a recommendation table, explain automatic downloads, and move command-line instructions to an optional manual section.
- Correct Windows notices to distinguish unavailable built-in models from locally installed Ollama models. Refresh old model suggestions and fix inconsistent Gemma tags.

## Capabilities

### New Capabilities

- `ollama-model-management`: User-driven Ollama selection, download, progress, installed-model inventory, disk-space guidance, deletion, and help across desktop platforms.

### Modified Capabilities

None. The existing `add-local-ollama-guidance` change introduced the initial terminology and help; this change specifies the additional end-to-end workflow.

## Impact

- Electron main/preload IPC for Ollama’s local HTTP API and model storage inspection.
- React setup wizard, Models page, Ollama manager page, Help article/modal, navigation and English/Russian/Spanish translations.
- Frontend and Electron tests. Ollama remains a separately installed dependency; PhotoRAG does not install or bundle it.
