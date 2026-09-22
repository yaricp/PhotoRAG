# Release plan notes

## Current release focus

The next release should prioritize a stable desktop app experience with remote models.

This release already contains enough risk and user-visible change:

- clean Windows first-run setup;
- dependency install locking and clearer setup progress;
- watcher/folder processing fixes;
- bundled template tags/categories for remote tagging and categorization;
- thumbnail loading improvements;
- chat draft and selected-photo persistence;
- clearer model labels;
- failed pipeline task retry and per-photo full pipeline rerun.

Must-fix before cutting the next release:

- Ensure every packaged installer includes `langchain-ollama` in the first-run backend venv. Ollama is exposed as a remote provider in the UI on every platform, and without this dependency vision/categorization tasks fail before they can call the local Ollama server.

Because of this, the release should not also include a full local-model support push or full auto-update implementation.

## Local models

Full local model support should be deferred to a separate release.

Reasons:

- Windows local mode has separate prerequisite problems, especially Microsoft Visual C++ Redistributable and Torch DLL loading.
- Local mode requires larger downloads, longer installation, and clearer progress reporting.
- CPU/GPU behavior needs dedicated testing.
- Model caches, venv state, and fallback behavior need reliable diagnostics.
- Mixing local-model stabilization into this release would make failures harder to diagnose and could make the whole app feel unstable even if remote mode works.

Recommended approach for the local-model release:

- Add prerequisite checks before offering local models.
- Detect and explain missing Visual C++ Redistributable on Windows.
- Run a small Torch/import self-test after dependency installation.
- Provide an explicit fallback to remote models.
- Improve local model download progress and recovery.
- Test Windows first, then macOS/Linux.

## Auto-updates

Do not include a full auto-update implementation in the current release.

Recommended staged plan:

1. Current release: manual update through the installer.
2. Next small release: update checker that detects a new version and opens the release/download page.
3. Later: download the full installer inside the app, verify SHA256, ask for confirmation, stop backend processes, run installer, quit app.
4. Defer delta/patch updates until release hosting, signing, and installer behavior are stable.

See also: `docs/auto_updates.md`.

## Recommended public positioning

For this release, describe PhotoRAG as ready for remote AI models first. Local processing should be presented as upcoming or experimental until the separate local-model release is tested well.
