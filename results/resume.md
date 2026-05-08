# Photo Describer 2 — Project Resume

> **Generated:** 2026-05-08
> **Current Focus:** Transitioning to Frontend (Electron + React) after Backend completion.

---

## 🎯 Main Goal Recall
To build a fully local, privacy-first, desktop application for organizing, tagging, describing, and searching photos. 
- **Tech Stack:** Electron (Desktop Shell) + ReactJS (Frontend SPA) + FastAPI (Backend) + SQLite (Storage & Queues) + Local AI Models.
- **Key Features:** Strict tiered ingestion (instant UI feedback vs slow background AI processing), semantic vector search, conversational AI Agent for natural language queries, and automatic organization of photos on the disk.

---

## ✅ Completed Milestones & Backend State

The Python backend is essentially **feature-complete** and ready to be consumed by the frontend.

1. **Ingestion & Observer Engine:**
   - Watchdog-based observer monitors directories, extracts EXIF creation dates, and **automatically moves photos** into structured `YYYY/MM/DD` directories.
   - Folder scanners now accurately calculate total processing steps and emit progress dynamically.

2. **3-Phase Deterministic AI Pipeline:**
   - **Phase 1:** Vision Description (Qwen-VL), OCR extraction (EasyOCR), and Keyword Tagging (CLIP).
   - **Phase 2:** Translation of descriptions to Russian (NLLB) and Document Text Embedding.
   - **Phase 3:** Final Vector Embedding (Nomic) of the synthesized content.
   - All managed via isolated `SqliteHuey` background queues.

3. **Conversational AI Agent (LangGraph):**
   - The conversational agent has been successfully integrated with full tool support (Search, Resize, EXIF, Categories, Tags).
   - State management is stable: The agent uses an `extract_photos` node to safely parse tool outputs into `Photo` schemas without forcing restrictive structured outputs on the main LLM.

4. **Database & API:**
   - `pgvector` equivalent achieved locally via `sqlite-vec`.
   - 14 REST endpoints fully implemented, tested, and aligned with Frontend schemas.

---

## 🏗 Current Work in Progress (Frontend)

We have officially started the **Frontend Implementation Plan (Electron-First)**.

- **Phase 0 (Scaffolding):** 
  - The `electron-vite` project has been scaffolded in `frontend/`.
  - We have initiated the TDD infrastructure setup (Vitest + Playwright + MSW).
  - Types and initial structures are being generated.

---

## 🚀 Next Steps

1. **Complete Frontend Phase 0 & 1:**
   - Finish configuring the Mock Service Worker (MSW) to mimic the 14 backend endpoints for testing.
   - Implement the Electron `Main` process logic (App protocol for local image serving, backend process spawning).

2. **Frontend UI Components (Phase 2 & 3):**
   - Build the design tokens (Dark Glassmorphism aesthetic).
   - Implement the `GalleryPage` to consume paginated photos from the SQLite DB.
   - Integrate the real-time polling/SSE logic to update the UI when background queues finish processing.

3. **Packaging:**
   - Ensure PyInstaller correctly bundles the FastAPI backend into a single executable.
   - Configure Electron Builder to wrap the React renderer and Python backend into a distributable `.app` / `.exe`.
