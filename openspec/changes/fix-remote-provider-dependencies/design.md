# Design: packaged provider support matrix

## Goal

Make provider availability deterministic. A provider shown in the packaged desktop UI must be installable and runnable from the first-run backend venv created from `backend/requirements.txt`.

## Initial support matrix

This is the intended baseline for the next release. Implementation may narrow a row only if the provider is hidden consistently in UI and tests.

| Provider | User-facing group | Capabilities | Required packaged dependency | Release decision |
|---|---|---|---|---|
| OpenAI | Cloud API | chat, vision, CLIP/tagging, OCR, translation, embedding | `langchain-openai` | Keep supported |
| Anthropic | Cloud API | chat, vision, CLIP/tagging, OCR, translation | `langchain-anthropic` | Keep supported after adding production requirement |
| Google Gemini AI Studio | Cloud API | chat, vision, CLIP/tagging, OCR, translation, embedding | `langchain-google-genai` | Keep supported after adding production requirement |
| Ollama at localhost | Local via Ollama | chat, vision, CLIP/tagging, OCR, translation, embedding | `langchain-ollama` | Keep supported, but move user-facing copy to local Ollama guidance |
| DeepL | Translation API | translation only | `requests` | Keep supported |
| LibreTranslate | Self-hosted translation API | translation only | `requests` | Keep supported |
| Google Vertex AI | Cloud API | chat currently exposed | `langchain-google-vertexai` plus GCP auth setup | Hide until packaged dependency and auth docs are added |
| Groq | Cloud API | chat currently exposed | `langchain-groq` | Hide until packaged dependency and docs are added |
| Mistral AI | Cloud API | chat currently exposed | `langchain-mistralai` | Hide until packaged dependency and docs are added |
| Together AI | Cloud API | chat currently exposed | `langchain-together` | Hide until packaged dependency and docs are added |
| Cohere | Cloud API | chat currently exposed | `langchain-cohere` | Hide until packaged dependency and docs are added |

## Test strategy

Add a small explicit provider matrix in source or tests. Tests should assert:

- every packaged-supported provider has its package in `backend/requirements.txt` unless it uses only already-packaged stdlib/`requests`;
- every provider shown by Models page and Setup Wizard exists in the matrix for that capability;
- hidden providers do not appear in rendered provider selects;
- backend construction paths for OpenAI, Anthropic, Google Gemini, Ollama, DeepL, and LibreTranslate can be imported or mocked without missing-package errors.

## Notes

Ollama remains an HTTP-backed backend integration internally, but its user-facing classification belongs to `add-local-ollama-guidance`.
