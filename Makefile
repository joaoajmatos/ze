# ── Ze — project Makefile ─────────────────────────────────────────────────────
# All targets run from the repo root.
# Backend commands delegate to uv inside ./backend.

.DEFAULT_GOAL := help
BACKEND  := backend
UV       := uv run --project $(BACKEND)

DB_SYNC_URL ?= postgresql+psycopg2://ze:ze@localhost:5432/ze
# alembic resolves script_location relative to cwd, so we cd into backend first
ALEMBIC     := cd $(BACKEND) && DATABASE_URL_SYNC=$(DB_SYNC_URL) uv run python -m alembic

# ── Help ──────────────────────────────────────────────────────────────────────
.PHONY: help
help:
	@echo ""
	@echo "  Ze — available targets"
	@echo ""
	@echo "  Setup"
	@echo "    install        Install backend dependencies"
	@echo ""
	@echo "  Database"
	@echo "    db-up          Start Postgres via docker-compose"
	@echo "    db-down        Stop Postgres"
	@echo "    db-reset       Drop + recreate the ze database"
	@echo "    migrate        Apply all pending migrations (upgrade head)"
	@echo "    migrate-down   Roll back one migration step"
	@echo "    migrate-status Show current migration revision"
	@echo "    migrate-history List all migrations"
	@echo ""
	@echo "  Development"
	@echo "    dev            Start backend dev server (uvicorn --reload)"
	@echo ""
	@echo "  Testing"
	@echo "    test           Run backend tests (excludes slow embedding tests)"
	@echo "    test-all       Run all backend tests including slow ones"
	@echo ""
	@echo "  Code quality"
	@echo "    lint           Lint backend (ruff)"
	@echo ""
	@echo "  Docker"
	@echo "    docker-up      Start all services via docker-compose"
	@echo "    docker-down    Stop all services"
	@echo "    docker-build   Build all Docker images"
	@echo ""

# ── Setup ─────────────────────────────────────────────────────────────────────
.PHONY: install

install:
	cd $(BACKEND) && uv sync

.PHONY: sync-ze-api-key
sync-ze-api-key:
	python3 tools/sync_ze_api_key.py $(if $(ZE_API_TOKEN),--token $(ZE_API_TOKEN))

# ── Database ──────────────────────────────────────────────────────────────────
.PHONY: db-up db-down db-reset migrate migrate-down migrate-status migrate-history

db-up:
	docker compose up -d postgres
	@echo "Waiting for Postgres to be ready..."
	@until docker compose exec -T postgres pg_isready -U ze -q; do sleep 1; done
	@echo "Postgres is ready."

db-down:
	docker compose stop postgres

db-reset:
	docker compose exec -T postgres psql -U ze -c "DROP DATABASE IF EXISTS ze"
	docker compose exec -T postgres psql -U ze -c "CREATE DATABASE ze"

migrate:
	$(ALEMBIC) upgrade head

migrate-down:
	$(ALEMBIC) downgrade -1

migrate-status:
	$(ALEMBIC) current

migrate-history:
	$(ALEMBIC) history --verbose

# ── Development ───────────────────────────────────────────────────────────────
.PHONY: dev dev-be

dev: dev-be

dev-be:
	cd $(BACKEND) && uv run uvicorn ze.api.app:app --reload --host 0.0.0.0 --port 8000

# ── Testing ───────────────────────────────────────────────────────────────────
.PHONY: test test-all

test:
	cd $(BACKEND) && uv run pytest --ignore=tests/test_embeddings.py -q

test-all:
	cd $(BACKEND) && uv run pytest -q

# ── Code quality ──────────────────────────────────────────────────────────────
.PHONY: lint lint-be

lint: lint-be

lint-be:
	cd $(BACKEND) && uv run ruff check ze tests

# ── Docker ────────────────────────────────────────────────────────────────────
.PHONY: docker-up docker-down docker-build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-build:
	docker compose build
