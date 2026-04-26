# Local Photo Management & Semantic Search MVP

## Goal Description
Build a local, FastAPI and ReactJS MVP application for organizing, tagging, and describing photos using local AI models. The system will operate decoupled (Frontend and Backend separate) during development, with an eventual trajectory to package as a standalone Electron application (`.exe` or `.app` via PyInstaller). 

It emphasizes strict tiered ingestion (fast data vs. slow AI data), purely vector-based visual search, and a segregated Conversational RAG agent.

## User Review Required
> [!IMPORTANT]  
> Please review this finalized specification describing the UI syncing and SQLite multiprocessing approach. If approved, I will transition out of **brainstorming** and create our actionable implementation backlog!

## Proposed Changes

### Core Architecture & Environment
- **Configuration-Driven AI Models**: Managed via a local `.env` file mapping. 
  - *API Key Strategy*: Even though the primary architecture downloads and runs models directly in local Python memory (which inherently requires no network connection or API key), the Langchain classes are configured via factories. You will configure a pseudo "Local" profile that bypasses credential checks, but you can instantly substitute a Cloud API Key/URL in your `.env` to fall back to a commercial API without changing the codebase. (Also, a `HUGGINGFACE_API_TOKEN` will be maintained to allow downloading gated models like Llama3).
  - Vision Describer: `Qwen/Qwen2-VL-2B-Instruct`
  - Vision Keyword Extractor: `OpenCLIP`
  - Vision Text Extractor: `Tesseract` (or `EasyOCR`)
  - Query & Photo Embedder: `nomic-ai/nomic-embed-text-v1.5`
- **Database**: PostgreSQL paired with the `pgvector` extension.
- **On-Demand Model Fetching**: The FastAPI server manages background tasks to dynamically download HuggingFace weights upon initial startup.

### Component 1: Two-Tier File Ingestion Worker (Backend)
To provide an immediate user experience and guarantee packaging compatibility, processing is isolated using a lightweight internal queue.

- **Process Supervisor (SQLite Multiprocessing Queue)**: To avoid Docker and keep the app bundled natively, FastAPI will use a lightweight task framework (like `Huey` or `Taskiq`) backed by a local SQLite file. This cleanly manages spawning distinct OS-level Python processes for heavy AI inference without blocking the web server.

- **Tier 1: Instant Registration (Synchronous)**
  - File watcher detects a new file.
  - Generates Hash & extracts EXIF.
  - Base record instantly commits to DB. React immediately updates UI.

- **Tier 2: Background AI Enrichment (Asynchronous via SQLite Queue)**
  - The SQLite queue safely routes the image sequentially through isolated AI sub-processes loaded in memory:
  - **Worker A**: `OpenCLIP` generates keywords.
  - **Worker B**: `OCR` scans text.
  - **Worker C**: `Qwen2-VL` generates description.
  - **Worker D**: `nomic-embed` calculates the vector.

### Component 2: The ReactJS User Interface & Real-time Sync
- **Server-Sent Events (SSE)**: The React frontend establishes a one-way SSE connection to FastAPI (`EventSource`). As the heavy background SQLite queue completes the AI tasks for a photo, FastAPI pushes a live lightweight JSON event to React. The UI dynamically populates the newly generated tags and categories without the user ever reloading the page.
- **Gallery & Semantic Search Page**:
  - Validates vector cosine-similarity lookup via Postgres `pgvector`.
- **Conversational AI Agent Page**:
  - Segregated Language Graph ReAct agent for querying the vector database.

## Open Questions
All workflows are fully specified. The path to compiling this into an Electron app using PyInstaller and SQLite is highly viable.

## Verification Plan
### Automated Tests
- Vector database integrity checks and Multiprocessing queue concurrency unit tests.
### Manual Verification
- Dropping 10 images reveals them instantly in React. Watching the UI magically populate with tags dynamically via the SSE connection minutes later as the SQLite Python processes complete their inference in the background.
