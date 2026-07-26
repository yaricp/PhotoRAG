# Photo Describer 2 — developer workflow.
# Requires: Python 3.13 + uv, Node 20 (see .nvmrc), GNU make.
SHELL := /bin/bash
BACKEND  := backend
FRONTEND := frontend
VENV     := $(BACKEND)/.venv
PY       := .venv/bin/python
VITEST   := node --require ./scripts/crypto-polyfill.cjs ./node_modules/.bin/vitest

.DEFAULT_GOAL := help

.PHONY: help init init-db openspec-setup lint format \
        test test-backend test-frontend dev dev-backend dev-frontend \
        ci ci-backend ci-frontend e2e clean

help: ## List available targets
	@grep -E '^[a-z0-9-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  \033[1m%-16s\033[0m %s\n", $$1, $$2}'

init: ## Install all dependencies (backend uv sync + frontend npm install + git hooks)
	cd $(BACKEND) && uv sync
	cd $(FRONTEND) && npm install

init-db: ## Initialise the backend DB schema (set APP_DATA_DIR to override the default data dir)
	cd $(BACKEND) && $(PY) init_db_only.py

openspec-setup: ## Install the OpenSpec CLI globally and refresh its instruction files
	npm install -g @fission-ai/openspec
	openspec update

lint: ## Lint backend (ruff) and frontend (eslint)
	cd $(BACKEND) && uvx ruff check .
	cd $(FRONTEND) && npm run lint

format: ## Format backend with ruff (black-style) and apply safe lint fixes
	cd $(BACKEND) && uvx ruff format . && uvx ruff check . --fix

test: test-backend test-frontend ## Run both test suites

test-backend: ## Run backend tests (heavy-ML tests are auto-excluded)
	cd $(BACKEND) && $(PY) -m pytest -q

test-frontend: ## Run frontend unit tests (vitest)
	cd $(FRONTEND) && $(VITEST) run

dev: ## Run the full app in dev mode (electron-vite; spawns the backend from backend/.venv)
	cd $(FRONTEND) && PATH="$(abspath $(VENV))/bin:$$PATH" npm run dev

dev-backend: ## Run the backend API standalone (run `make init-db` once first)
	cd $(BACKEND) && $(PY) run.py

dev-frontend: ## Alias for `make dev` (the Electron dev server owns the backend process)
	$(MAKE) dev

ci: ci-backend ci-frontend ## Mirror the GitHub Actions CI jobs locally

ci-backend: ## Backend CI: ruff check + format check + pytest with coverage gate
	cd $(BACKEND) && uvx ruff check . && uvx ruff format --check .
	cd $(BACKEND) && uv run --with pytest-cov python -m pytest tests/ -v --cov=src --cov-fail-under=42

ci-frontend: ## Frontend CI: eslint + tsc + vitest with coverage
	cd $(FRONTEND) && npm run lint && npm run type-check
	cd $(FRONTEND) && $(VITEST) run --coverage

e2e: ## Run Playwright E2E tests (run `npx playwright install` once to fetch browsers)
	cd $(FRONTEND) && npm run test:e2e

clean: ## Remove local environments and caches to reclaim disk space
	rm -rf $(VENV) $(FRONTEND)/node_modules $(FRONTEND)/coverage $(FRONTEND)/out $(FRONTEND)/dist-electron
	rm -rf $(BACKEND)/.pytest_cache $(BACKEND)/.coverage .pytest_cache
	find . -type d -name __pycache__ -not -path "./$(FRONTEND)/node_modules/*" -prune -exec rm -rf {} + 2>/dev/null || true
