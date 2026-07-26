# Design: remove-unused-deps

## Decisions (user-approved 2026-07-26)

1. **Depth: packages + all dead code.** The project becomes honestly SQLite-only; Postgres support returns via git history if ever needed.
2. **Scope: backend + frontend** in one change; removal list requires explicit per-package user approval after the audit.

## Audit method

- Backend: `deptry` run from the project venv (`backend/.venv`) against `src/`, mapped to `requirements.txt`/`pyproject.toml`. deptry cannot see dynamic imports, so every candidate is cross-checked by grep before entering the removal list.
- Frontend: `npx depcheck` in `frontend/`; candidates cross-checked against build scripts (`electron-builder`, vite configs) which use packages without importing them.

## Risk classes

| Class | Example | Policy |
|---|---|---|
| Provably dead (declared, never imported, no runtime role) | `pgvector` | Remove |
| Dynamically imported | `langchain-openai` via `init_chat_model` | Keep, document |
| Runtime deps of the ML stack (no direct import) | `accelerate`, `einops`, `qwen-vl-utils` | Keep unless proven unused |
| Build-time only (frontend) | `electron-builder` plugins | Keep, document |

## Verification strategy

No new production code is written, so classic RED-GREEN does not apply. The safety net is: (a) green baseline recorded before changes (backend 403 passed / 1 skipped, frontend 243 passed); (b) removed packages are `pip uninstall`-ed from the venv before the final test run, proving nothing imports them transitively; (c) backend smoke start with healthcheck endpoint; (d) `tsc --noEmit` for the frontend.

## Rollout

Small commits per cluster (spec, backend code, backend deps, frontend deps, verification fixes) on branch `remove-unused-deps`, then code review + security review, then merge/PR per user choice.
