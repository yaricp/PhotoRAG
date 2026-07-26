# Change: Remove unused dependencies and dead Postgres code

## Why

The backend declares packages that are never used (confirmed: `pgvector` — imported under try/except in `models.py`, but the `Vector` type is not used in any column). Legacy Postgres scaffolding (`docker-compose.yml`, the non-SQLite DSN branch in `db/database.py`) survives from an earlier design although the product ships as an Electron desktop app with embedded SQLite + sqlite-vec. Unused packages inflate installer size, slow down first-run setup (the wizard pip-installs requirements on the user machine), and mislead readers about the real architecture.

## What Changes

- Audit backend (`requirements.txt`, `requirements-ci.txt`, `pyproject.toml`) with deptry + manual grep cross-check; audit frontend (`package.json`) with depcheck.
- Remove packages confirmed unused **and approved by the user** (per-package approval list).
- Remove dead Postgres code: guarded `pgvector` import in `src/models.py`, pgvector mocks in tests, Postgres DSN branch in `src/db/database.py`, `backend/docker-compose.yml`. The backend becomes explicitly SQLite-only.
- Sync `uv.lock` and frontend lockfile.

## Non-goals

- No behavior changes to the photo pipeline, API, or UI.
- ML-stack packages without direct imports but required at runtime by transformers/model loading (e.g. `accelerate`, `einops`, `qwen-vl-utils`) are NOT removed unless proven unused at runtime.

## Impact

- Affected specs: `persistence` (new: SQLite-only requirement)
- Affected code: `backend/requirements*.txt`, `backend/pyproject.toml`, `backend/uv.lock`, `backend/src/models.py`, `backend/src/db/database.py`, `backend/docker-compose.yml` (deleted), test files with pgvector mocks, `frontend/package.json` + lockfile.
- Verification: packages are uninstalled from the local venv and the full test suites must stay green (backend 403+1, frontend 243), plus backend smoke start.
