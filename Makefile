# ── Ze — project Makefile ─────────────────────────────────────────────────────

.DEFAULT_GOAL := help

DB_SYNC_URL ?= postgresql+psycopg2://ze:ze@localhost:5432/ze
ALEMBIC     := DATABASE_URL_SYNC=$(DB_SYNC_URL) uv run python -m alembic

# ── Help ──────────────────────────────────────────────────────────────────────
.PHONY: help
help:
	@echo ""
	@echo "  Ze — available targets"
	@echo ""
	@echo "  Setup"
	@echo "    install              Install dependencies"
	@echo "    google-auth          One-time Google OAuth2 flow (Calendar + Gmail)"
	@echo "    generate-ze-api-key  Generate or refresh ZE_API_KEY in .env"
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
	@echo "    dev            Start dev server (uvicorn --reload, REST API only)"
	@echo "    dev-poll       Start Telegram long-polling (interact via Telegram locally)"
	@echo "    dev-eval       Start REST API without Telegram webhook (for running evals)"
	@echo ""
	@echo "  Eval (requires 'make dev-eval' running)"
	@echo "    eval-server    Start MCP eval server (for Claude Code / Cursor / Codex)"
	@echo "    eval-clean     Delete eval-namespaced rows from DB (routing_log, checkpoints, cost_log)"
	@echo ""
	@echo "  Testing"
	@echo "    test           Run tests (excludes slow embedding tests)"
	@echo "    test-all       Run all tests including slow ones"
	@echo ""
	@echo "  Code quality"
	@echo "    lint           Lint with ruff"
	@echo ""
	@echo "  Docker"
	@echo "    docker-up      Start all services via docker-compose"
	@echo "    docker-down    Stop all services"
	@echo "    docker-build   Build all Docker images"
	@echo ""

# ── Setup ─────────────────────────────────────────────────────────────────────
.PHONY: install google-auth generate-ze-api-key

install:
	uv sync

google-auth:
	uv run python scripts/google_auth.py

generate-ze-api-key:
	uv run python scripts/generate_ze_api_key.py $(if $(ZE_API_TOKEN),--token $(ZE_API_TOKEN))

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
.PHONY: dev dev-poll dev-eval

dev:
	LOG_FILE=logs/ze.log uv run uvicorn ze.api.app:app --reload --host 0.0.0.0 --port 8000

dev-poll:
	LOG_FILE=logs/ze.log uv run python -m ze.dev_poll

dev-eval:
	PUBLIC_URL= LOG_FILE=logs/ze.log uv run uvicorn ze.api.app:app --reload --host 0.0.0.0 --port 8000

# ── Eval ──────────────────────────────────────────────────────────────────────
.PHONY: eval-server eval-clean

eval-server:
	uv run python evals/mcp_server.py

eval-clean:
	@echo "Removing eval-namespaced rows from routing_log, checkpoints, llm_cost_log..."
	docker compose exec -T postgres psql -U ze -d ze -c \
		"DELETE FROM routing_log WHERE session_id LIKE 'eval-%';"
	docker compose exec -T postgres psql -U ze -d ze -c \
		"DELETE FROM llm_cost_log WHERE session_id LIKE 'eval-%';"
	docker compose exec -T postgres psql -U ze -d ze -c \
		"DELETE FROM checkpoint_blobs WHERE thread_id LIKE 'eval-%';"
	docker compose exec -T postgres psql -U ze -d ze -c \
		"DELETE FROM checkpoint_writes WHERE thread_id LIKE 'eval-%';"
	docker compose exec -T postgres psql -U ze -d ze -c \
		"DELETE FROM checkpoints WHERE thread_id LIKE 'eval-%';"
	@echo "Done. Note: user_facts and episodes written before this fix was deployed"
	@echo "cannot be isolated by eval session. Delete them manually if needed:"
	@echo "  docker compose exec -T postgres psql -U ze -d ze"
	@echo "  then: SELECT key, value, updated_at FROM user_facts ORDER BY updated_at DESC LIMIT 20;"

# ── Testing ───────────────────────────────────────────────────────────────────
.PHONY: test test-all

test:
	uv run pytest --ignore=tests/test_embeddings.py -q

test-all:
	uv run pytest -q

# ── Code quality ──────────────────────────────────────────────────────────────
.PHONY: lint

lint:
	uv run ruff check ze tests

# ── Docker ────────────────────────────────────────────────────────────────────
.PHONY: docker-up docker-down docker-build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-build:
	docker compose build
