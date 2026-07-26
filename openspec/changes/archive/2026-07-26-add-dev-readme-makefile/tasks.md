# Tasks: add-dev-readme-makefile

## 1. Makefile
- [x] 1.1 Write root Makefile with targets: init, init-db, openspec-setup, lint, format, test, test-backend, test-frontend, dev, dev-backend, dev-frontend, ci, e2e, clean
- [x] 1.2 Verify on fresh worktree: `make init` creates backend/.venv (uv sync) and frontend/node_modules
- [x] 1.3 Verify: `make lint`, `make test`, `make ci` pass; `make init-db` + backend smoke boots; `make clean` reclaims space

## 2. README
- [x] 2.1 Write root README.md for contributors (overview, architecture, repo map, prerequisites, quickstart, testing, workflow, CI)
- [x] 2.2 Cross-check every command in README against actual Makefile/scripts

## 3. Review & completion
- [x] 3.1 Code review of the diff
- [x] 3.2 security-review before merge
- [x] 3.3 Merge per user choice; archive change
