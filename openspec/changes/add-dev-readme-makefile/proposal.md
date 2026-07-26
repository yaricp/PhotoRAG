# Change: Add contributor README and root Makefile

## Why

The repository has no root README — a visitor cannot tell what the project is, how it is structured, or how to set up a dev environment. Common actions (install, lint, format, test, dev run, CI mirror) require memorizing per-directory commands that differ between backend (uv/pytest/ruff) and frontend (npm/vitest/eslint).

## What Changes

- Add root `README.md` targeted at developers/contributors (English): project overview, architecture summary, repo map, prerequisites, quickstart via make, testing/quality guide (incl. heavy-ML test exclusion), OpenSpec + conventional-commit workflow, CI overview, pointer to `README-installer.md` for end users.
- Add root `Makefile` orchestrating both halves: `init`, `init-db`, `openspec-setup`, `lint`, `format`, `test`/`test-backend`/`test-frontend`, `dev`/`dev-backend`/`dev-frontend`, `ci`, `e2e`, `clean`.
- Formatting uses `ruff format` (black-style, already enforced by CI via `ruff format --check`); no separate black or prettier is introduced.

## Non-goals

- No end-user documentation (separate task: user guide + GitHub Pages one-pager).
- No changes to application code, CI workflows, or dependencies.

## Impact

- Affected specs: `developer-tooling` (new capability)
- Affected files: `README.md` (new), `Makefile` (new). Verification: every make target executed successfully on a fresh worktree (`make init` onward).
