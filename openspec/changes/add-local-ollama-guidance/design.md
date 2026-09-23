# Design: local Ollama guidance

## Goal

Make Ollama understandable as a local model path when it is installed on the user's own computer and accessed through `http://localhost:11434`.

Internally, PhotoRAG can keep routing Ollama through the existing HTTP provider path. The product language should distinguish it from cloud APIs because the user setup, privacy expectation, and failure modes are different.

## User-facing model groups

| Group | Meaning | Examples |
|---|---|---|
| Built-in local | PhotoRAG downloads and loads the model directly in the backend venv | Qwen/HuggingFace vision, local CLIP, local NLLB |
| Local via Ollama | User installs Ollama separately; PhotoRAG talks to the local Ollama server | `http://localhost:11434`, no API key |
| Cloud API | Requests go to a third-party provider over the internet | OpenAI, Anthropic, Google Gemini |

## Help topic content

The local Ollama help topic should cover:

- what Ollama is in PhotoRAG;
- official download link: `https://ollama.com/download`;
- default local server URL: `http://localhost:11434`;
- server check commands:
  - `ollama --version`
  - `curl http://localhost:11434/api/version`
- model pull commands:
  - `ollama pull qwen2.5vl:3b`
  - `ollama pull qwen2.5vl:7b`
  - `ollama pull nomic-embed-text`
  - `ollama pull mxbai-embed-large`
  - `ollama pull gemma3:4b`
- how to paste the same model names into PhotoRAG's Models page.

## Initial model recommendations

| PhotoRAG capability | Fast/small | Better quality | Notes |
|---|---|---|---|
| Vision descriptions | `qwen2.5vl:3b` | `qwen2.5vl:7b` | Main photo description path; 7B needs more memory but should describe scenes better |
| OCR from images | `qwen2.5vl:3b` | `qwen2.5vl:7b` | Local OCR quality depends heavily on the vision model |
| Tags and categories | `qwen2.5vl:3b` | `qwen2.5vl:7b` | Remote-CLIP replacement path uses a vision LLM to classify against candidate names |
| Embeddings/search | `nomic-embed-text` | `mxbai-embed-large` | Embedding models power semantic search and reindexing |
| Chat | `gemma3:4b` | `gemma3:12b` | Chat can use a text model; it does not need image input for normal RAG answers |
| Translation | `gemma3:4b` | `gemma3:12b` | Good enough for experiments; cloud translation may still be better for production multilingual use |

## UX details

- The provider option should read "Ollama (local)" or "Local via Ollama".
- The default URL placeholder should remain `http://localhost:11434`.
- The API key field should stay hidden for Ollama.
- The UI should include a link to the local Ollama help topic near the Ollama hint.
- Privacy copy should say that localhost Ollama keeps data on the user's computer. Custom non-local Ollama URLs should be described as sending data to that configured server.
