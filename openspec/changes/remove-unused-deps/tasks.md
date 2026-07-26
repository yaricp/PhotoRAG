# Tasks: remove-unused-deps

## 1. Audit (no removals)
- [x] 1.1 Install deptry into `backend/.venv`; run against backend sources and requirement files
- [x] 1.2 Cross-check every deptry candidate with grep for dynamic/lazy imports
- [x] 1.3 Run `npx depcheck` in `frontend/`; cross-check candidates against build scripts and configs
- [x] 1.4 Present findings table; obtain user approval of the exact removal list

## 2. Backend dead code removal
- [x] 2.1 Remove guarded `pgvector` import from `src/models.py`
- [x] 2.2 Remove pgvector `sys.modules` mocks from affected test files
- [x] 2.3 Remove Postgres DSN branch and non-SQLite settings from `src/db/database.py` / `src/config.py`
- [x] 2.4 Delete `backend/docker-compose.yml`
- [x] 2.5 Run backend test suite — green

## 3. Dependency removal (approved list only)
- [x] 3.1 Remove approved packages from `requirements.txt`, `requirements-ci.txt`, `pyproject.toml`; sync `uv.lock`
- [x] 3.2 Remove approved packages from `frontend/package.json`; update lockfile
- [x] 3.3 `pip uninstall` removed packages from `backend/.venv`

## 4. Verification
- [x] 4.1 Full backend pytest run — green (baseline: 403 passed, 1 skipped)
- [x] 4.2 Frontend `vitest run` green (baseline: 243 passed) + `tsc --noEmit` clean
- [x] 4.3 Smoke-start backend; `GET /api/system/status/` responds OK

## 5. Review & completion
- [ ] 5.1 Code review of the full diff
- [ ] 5.2 security-review before merge
- [ ] 5.3 Merge / PR per user choice; archive change
