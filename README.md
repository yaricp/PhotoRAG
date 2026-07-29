# Photo Describer 2 (PhotoRAG)

A local-first desktop app that catalogs your photo library with AI: vision-model descriptions, OCR, CLIP tagging, semantic search, duplicate detection, and EXIF geo-mapping. Everything runs on your machine by default; remote model providers are optional.

License: MIT (see [LICENSE](LICENSE); third-party components audited in [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md)).

**This README is for developers and contributors.** End users: see [README-installer.md](README-installer.md) for installation guides.

## Architecture

- **Frontend** — Electron + React/TypeScript ([electron-vite](https://electron-vite.org/)). The Electron main process spawns the backend, picks a free port from 8000 upward, and polls `GET /api/system/status/` until it is healthy (`frontend/electron/main/backend.ts`). Runtime logs go to `photorag.log` in the Electron `userData` dir.
- **Backend** — Python 3.13 + FastAPI (`backend/src/main.py`), started by `backend/run.py`, which also launches a [Huey](https://github.com/coleifer/huey) worker for every pipeline stage running in `local` mode (vision, CLIP, embedding, translation, OCR — plus folder scan, which always runs; `backend/src/queues/`), each with its own SQLite queue storage.
- **Storage** — SQLite only, with the [sqlite-vec](https://github.com/asg017/sqlite-vec) extension for vector search. WAL mode and a 30 s busy timeout are set on every connection (`backend/src/db/database.py`).
- **AI models** — each stage runs `local` or `remote` (per-type `*_MODE` settings in `backend/src/config.py`, overridable at runtime via the `ai_model_configs` table):
  - Local defaults: Qwen2-VL (descriptions), OpenCLIP (tags), nomic-embed (search), NLLB (translation), EasyOCR (text).
  - Remote: any provider supported by LangChain `init_chat_model` (OpenAI, Anthropic, Google, Ollama, Groq, Mistral, Together, Cohere, or any OpenAI-compatible `base_url`). In remote mode, OCR and CLIP tagging are performed by a vision-capable LLM with structured prompts (`backend/src/model_services.py`).
- **AI agent** — LangGraph-based chat agent with photo-library tools (`backend/src/graphs/`).

## Repository map

| Path | Contents |
|---|---|
| `backend/` | FastAPI app, pipeline tasks, queues, AI model adapters, tests |
| `frontend/` | Electron + React app, e2e tests, installer configs |
| `openspec/` | Specs and change proposals ([OpenSpec](https://github.com/Fission-AI/OpenSpec) spec-driven workflow) |
| `scripts/` | Installer bundling and integration-test scripts |
| `.github/workflows/` | CI (lint, tests, coverage), release builds, release-please |

## Prerequisites

- **Python 3.13** and [uv](https://docs.astral.sh/uv/)
- **Node 20** (`.nvmrc` is set; `nvm use`)
- GNU make

## Quickstart

```bash
make init   # backend: uv sync (incl. dev deps) · frontend: npm install (+ git hooks)
make test   # backend pytest + frontend vitest
make dev    # full app in dev mode (Electron spawns the backend)
```

Run `make` with no arguments to list all targets.

| Target | Purpose |
|---|---|
| `make init` | Install all dependencies into project-local environments |
| `make init-db` | Create the backend DB schema (first run; `APP_DATA_DIR=<dir>` to override) |
| `make lint` / `make format` | Ruff + ESLint / ruff format (black-style) |
| `make test`, `test-backend`, `test-frontend` | Test suites |
| `make dev`, `dev-backend`, `dev-frontend` | Full app / standalone API / alias for `dev` |
| `make ci`, `ci-backend`, `ci-frontend` | Mirror the GitHub Actions jobs locally before pushing |
| `make e2e` | Playwright renderer tests (`npx playwright install` once beforehand) |
| `make openspec-setup` | Install/refresh the OpenSpec CLI |
| `make clean` | Delete venv, node_modules, and caches to reclaim disk |

### Dev-mode notes

- In dev, Electron spawns `python3` from `PATH`; `make dev` prepends `backend/.venv/bin` so the project venv is used automatically.
- `make dev-backend` runs the API alone against the default app-data dir (macOS: `~/Library/Application Support/PhotoRAG`). Run `make init-db` once first, or point both at a sandbox: `APP_DATA_DIR=/tmp/pd2 make init-db dev-backend`.
- `make clean` also removes `frontend/node_modules`, which the git hooks (lint-staged, commitlint) run from — after a clean, run `make init` again before committing.

## Testing notes

- **Backend** (~400 tests): heavy-ML tests (25 files needing torch/easyocr/open-clip) are excluded automatically via `conftest.collect_ignore`; the remaining tests mock heavy modules. CI installs the lightweight `backend/requirements-ci.txt` and enforces a 42% coverage floor.
- **Frontend** (~240 tests): vitest + Testing Library; `make ci-frontend` adds the coverage run.
- **E2E**: Playwright against the built renderer.

## Contribution workflow

1. **Specs first (OpenSpec).** Each task gets a change proposal under `openspec/changes/<task>/` (see `/opsx:propose` command or the OpenSpec docs). Specs are committed and reviewed in the PR together with the code; on completion the change is archived into `openspec/specs/`.
2. **Conventional commits** are enforced by commitlint (husky `commit-msg` hook). The `pre-commit` hook runs lint-staged and `tsc --noEmit`.
3. **Before pushing:** `make ci` must pass.
4. **Releases** are automated with release-please; installer builds run in `.github/workflows/build.yml` (see `README-installer.md` for artifacts).

## Production install flow (context for contributors)

The packaged app bundles a standalone Python; the first-run wizard creates a venv in the Electron `userData` dir and pip-installs `backend/requirements.txt` on the user's machine (`frontend/electron/main/ipc.ts`). Keep `requirements.txt` (production), `backend/pyproject.toml` + `uv.lock` (development), and `requirements-ci.txt` (CI) consistent when touching dependencies.
