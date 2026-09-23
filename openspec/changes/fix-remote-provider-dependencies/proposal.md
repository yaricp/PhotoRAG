# Change: Fix remote provider dependency consistency

## Why

The Models page and Setup Wizard expose multiple remote AI providers, but the packaged backend venv is built from `backend/requirements.txt`, not from the development dependency set in `backend/pyproject.toml`.

The current production requirements include OpenAI and Ollama support, while the UI also offers Anthropic, Google Gemini, Groq, Mistral, Together, Cohere, DeepL, and LibreTranslate in some model paths. Some of these providers are imported directly by backend code, and others rely on LangChain provider packages that may not be installed in a packaged app. This can make a provider look supported in the UI but fail at runtime after the user has already configured it.

Because the next release focuses on stable desktop use with configured model providers, provider availability must be explicit, tested, and consistent across the UI, development dependencies, and packaged installer requirements.

## What Changes

- Define the supported packaged provider matrix for every model capability: vision, CLIP/tagging, OCR, embedding, translation, and chat.
- Make the UI provider options match the provider matrix instead of exposing providers that the packaged app cannot run.
- Keep `backend/pyproject.toml`, `backend/requirements.txt`, and any provider-specific backend imports in sync.
- Add tests that fail when a provider exposed by the frontend is missing its required packaged dependency or backend support path.
- Make unsupported providers either hidden or clearly marked unavailable until their dependencies and backend paths are included.
- Update release planning notes so the old `langchain-ollama` must-fix is recorded as complete and the remaining provider consistency work is tracked explicitly.

## Non-goals

- Does not redesign the Models page UX beyond provider availability and labeling needed for correctness.
- Does not add new cloud providers beyond the ones already exposed or intentionally retained.
- Does not implement global remote API throttling or rate-limit scheduling.
- Does not change the local Ollama user guidance; that is handled by `add-local-ollama-guidance`.

## Impact

- Affected specs: `model-configuration`
- Affected files: `backend/pyproject.toml`, `backend/requirements.txt`, `backend/src/model_services.py`, `backend/src/ai/registry.py`, `frontend/src/pages/ModelsPage.tsx`, `frontend/src/pages/SetupWizard/StepModelConfig.tsx`, frontend/backend tests, `docs/release_plan.md`
- Verification: TDD tests for provider matrix consistency, targeted frontend provider rendering tests, targeted backend import/provider tests, and local CI where available.
