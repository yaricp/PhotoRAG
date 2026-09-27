# Tasks: add-local-ollama-guidance

## 1. Specify local Ollama behaviour
- [x] 1.1 Add the OpenSpec delta for "Local via Ollama" terminology and guidance
- [x] 1.2 Define the first recommended Ollama model table for each PhotoRAG capability

## 2. TDD: Ollama UI and help coverage
- [x] 2.1 Add failing tests that Ollama is labeled as local/server-local rather than cloud remote in Models page and Setup Wizard
- [x] 2.2 Add failing tests that Ollama does not show an API key field and defaults to `http://localhost:11434`
- [x] 2.3 Add failing tests that Ollama embedding suggestions include `nomic-embed-text` and `mxbai-embed-large`
- [x] 2.4 Add failing help-page tests for the new local Ollama topic and sidebar link

## 3. Implement local Ollama UX
- [x] 3.1 Update Models page and Setup Wizard copy for "Local via Ollama"
- [x] 3.2 Add or refine Ollama-specific hints, defaults, and model suggestions per capability
- [x] 3.3 Add a visible path from model configuration to the local Ollama help topic
- [x] 3.4 Add local Ollama help content covering install, server check, model pulls, and model recommendations
- [x] 3.5 Update privacy copy so local Ollama is described separately from cloud remote providers
- [x] 3.6 Update public docs/site copy if it currently groups local Ollama with remote providers

## 4. Verify
- [x] 4.1 Run the new Ollama UI/help tests and confirm they fail before implementation and pass after
- [x] 4.2 Run targeted Models page, Setup Wizard, and Help page tests
- [x] 4.3 Manually review the rendered help topic in Russian and English
- [x] 4.4 Run full frontend CI where available
