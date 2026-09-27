# Change: Add local Ollama guidance

## Why

PhotoRAG currently presents Ollama as a remote provider because the backend talks to it over HTTP. For users, that is misleading when Ollama is installed on the same computer and served from `http://localhost:11434`: their photos and prompts stay local, no API key is needed, and the setup path is closer to local models than to cloud providers.

Users who want to try local models through Ollama need an obvious path from the Models page: install Ollama, pull the right models, test the local server, choose sensible model names for each PhotoRAG capability, and understand resource tradeoffs. Today those steps are scattered or implied.

## What Changes

- Present Ollama in the product as "Local via Ollama" / "Локально через Ollama" rather than as a normal remote cloud provider.
- Add in-app help for installing Ollama, checking the local server, pulling models, and mapping models to PhotoRAG capabilities.
- Add model recommendations for vision descriptions, OCR, tagging/categorization, embeddings/search, chat, and translation, with practical size/performance notes.
- Add Ollama embedding suggestions, including `nomic-embed-text` and `mxbai-embed-large`.
- Add a Models page path that helps the user verify `http://localhost:11434` and understand that Ollama does not need an API key.
- Link to official Ollama download and model library pages from help/documentation.

## Non-goals

- Does not bundle Ollama itself or install it automatically.
- Does not download Ollama models from inside PhotoRAG unless explicitly implemented in a later change.
- Does not replace the existing backend HTTP integration for Ollama.
- Does not solve all built-in local model support issues on Windows; Ollama is a separate local-server path.
- Does not decide final cloud provider packaging; that is handled by `fix-remote-provider-dependencies`.

## Impact

- Affected specs: `model-configuration`
- Affected files: `frontend/src/pages/ModelsPage.tsx`, `frontend/src/pages/SetupWizard/StepModelConfig.tsx`, help routing/content/i18n files under `frontend/src`, frontend tests, possibly `site/` and `README-installer.md`
- Verification: TDD tests for Ollama labeling/help links/model suggestions, targeted UI tests, and manual review of the help page in English/Russian at minimum.
