# ── Ze — project Makefile ─────────────────────────────────────────────────────

.DEFAULT_GOAL := help

ZE      := apps/ze-api
ZE_CORE := core/engine/ze-core
ZE_WEB  := apps/ze-web

LOG_FILE     ?= $(ZE)/logs/ze.log
# Config overlay config/profiles/$(ZE_PROFILE).yaml for the dev targets: no unattended LLM jobs.
# `make dev ZE_PROFILE=` runs the shipped config as is.
ZE_PROFILE   ?= quiet
# A DATABASE_URL_SYNC in the environment (a floor's throwaway DB) wins over the shared dev DB.
DB_SYNC_URL  ?= $(or $(DATABASE_URL_SYNC),postgresql+psycopg2://ze:ze@localhost:5432/ze)
DB_NAME      := $(firstword $(subst ?, ,$(lastword $(subst /, ,$(DB_SYNC_URL)))))
ZE_MIGRATE   := cd $(ZE) && DATABASE_URL_SYNC=$(DB_SYNC_URL) uv run python -m ze_api.cli.migrate

# ── Help ──────────────────────────────────────────────────────────────────────
.PHONY: help
help:
	@echo ""
	@echo "  Ze — available targets"
	@echo ""
	@echo "  Setup"
	@echo "    install              Install Python workspace dependencies (uv sync)"
	@echo "    web-install          Install React web app dependencies (bun install)"
	@echo "    google-auth          One-time Google OAuth2 flow (Calendar + Gmail)"
	@echo "    generate-ze-api-key  Generate or refresh ZE_API_KEY in .env"
	@echo ""
	@echo "  Database"
	@echo "    db-up            Start Postgres via docker-compose"
	@echo "    db-down          Stop Postgres"
	@echo "    db-reset         Drop + recreate the database named in DB_SYNC_URL (default ze) and apply all migrations"
	@echo "    reset-personal-state  Delete learned personal state after CONFIRM=RESET"
	@echo "    migrate          Apply all pending migrations (upgrade heads); honors DATABASE_URL_SYNC / DB_SYNC_URL, default is the shared dev DB ze"
	@echo "    migrate-down     Roll back one migration step"
	@echo "    migrate-status   Show current migration revision"
	@echo "    migrate-history  List all migrations"
	@echo "    migrate-stamp    Stamp existing DB to squashed heads (run once after squash)"
	@echo ""
	@echo "  Workspace sidecar"
	@echo "    workspace-up     Start the workspace sidecar via docker-compose (:8081)"
	@echo "    workspace-down   Stop the workspace sidecar"
	@echo ""
	@echo "  Development"
	@echo "    dev              Start backend (uvicorn --reload on :8000); also brings up the workspace sidecar"
	@echo "                     dev targets use ZE_PROFILE=$(ZE_PROFILE) (quiet: no unattended LLM jobs); ZE_PROFILE= for the full config"
	@echo "    seed             Apply dev narrative fixtures to the database"
	@echo "    db-reset-seed    Reset DB, migrate, and apply dev fixtures"
	@echo "    web              Start React web app (bun dev on :5173)"
	@echo "    dev-full         Start backend + React web app + workspace sidecar (Ctrl-C stops backend/web)"
	@echo "    dev-eval         Start backend in eval mode: no dev seed data, PUBLIC_URL cleared, background jobs still start"
	@echo "    logs             Tail the server log file (LOG_FILE=$(LOG_FILE))"
	@echo ""
	@echo "  Web app"
	@echo "    web-install      Install React web app dependencies (bun install)"
	@echo "    web              Start React web dev server (:5173)"
	@echo "    web-build        Build React web app for production"
	@echo "    web-test         Run @myguyze/ze-ui + ze-web tests (vitest) — alias for test-web"
	@echo ""
	@echo "  Eval (requires 'make dev-eval' running)"
	@echo "    eval             Run full eval suite — routing accuracy only (cheap)"
	@echo "    eval-judge       Run eval suite with LLM quality judge (costs tokens)"
	@echo "    eval-report      Show last eval run summary"
	@echo "    eval-diff        Compare last two eval runs (regression detection)"
	@echo "    eval-server      Start MCP eval server (for Claude Code / Cursor / Codex)"
	@echo "    calibrate-commitment-intake  LIVE System One + old-pipeline baseline over eval/calibration/commitment_intake.jsonl; costs credits (needs OPENROUTER_API_KEY); --check-sets is offline"
	@echo "    calibrate-routing  LIVE System One run over eval/calibration/routing.jsonl; costs credits (needs OPENROUTER_API_KEY); --check-sets is offline"
	@echo "    calibrate-skills   LIVE System One run over eval/calibration/skills.jsonl; costs credits (needs OPENROUTER_API_KEY); --recall is offline"
	@echo "    calibrate-loop-gate  LIVE System One + Haiku baseline over eval/calibration/loop_gate.jsonl; costs credits (needs OPENROUTER_API_KEY); --check-sets is offline"
	@echo "    calibrate-corroboration  LIVE System One + E5 baseline over eval/calibration/corroboration.jsonl; costs credits"
	@echo "    calibrate-complexity  LIVE System One over eval/calibration/complexity.jsonl; costs credits (--check-sets offline; --set holdout = the one verdict run)"
	@echo "    calibrate-open-query  LOCAL E5 run over eval/calibration/open_query.jsonl; free; --check-sets is offline"
	@echo "    eval-clean       Delete eval-namespaced rows from DB"
	@echo ""
	@echo "  Testing (see docs/testing.md)"
	@echo "    test / test-api      Run ze-api tests (skips slow)"
	@echo "    test-core            Run ze-core tests"
	@echo "    test-logging         Run ze-logging tests"
	@echo "    test-agents          Run ze-agents tests"
	@echo "    test-plugin          Run ze-plugin tests"
	@echo "    test-sdk             Run ze-sdk tests"
	@echo "    test-proactive       Run ze-proactive tests"
	@echo "    test-memory          Run ze-memory tests"
	@echo "    test-onboarding      Run ze-onboarding tests"
	@echo "    test-seed            Run ze-seed tests"
	@echo "    test-correlation     Run ze-correlation tests"
	@echo "    test-browser         Run ze-browser tests"
	@echo "    test-notifications   Run ze-notifications tests"
	@echo "    test-components      Run ze-components tests"
	@echo "    test-eval            Run ze-eval tests"
	@echo "    test-google          Run ze-google tests"
	@echo "    test-ingestion       Run ze-ingestion tests"
	@echo "    test-automation      Run ze-automation tests"
	@echo "    test-worldstate      Run ze-worldstate tests"
	@echo "    test-priority        Run ze-priority tests"
	@echo "    test-skills          Run ze-skills tests"
	@echo "    test-workspace       Run ze-workspace tests"
	@echo "    test-collision       Run ze-collision tests"
	@echo "    test-trading212      Run ze-trading212 tests"
	@echo "    test-yt              Run ze-yt tests"
	@echo "    test-finance         Run ze-finance tests"
	@echo "    test-workspace-sidecar  Run workspace sidecar tests"
	@echo "    test-personal        Run ze-personal tests"
	@echo "    test-communication   Run ze-communication tests"
	@echo "    test-messenger       Run ze-messenger tests"
	@echo "    test-calendar        Run ze-calendar tests"
	@echo "    test-prospecting     Run ze-prospecting tests"
	@echo "    test-news            Run ze-news tests"
	@echo "    test-web / web-test  Run @myguyze/ze-ui + ze-web tests (vitest)"
	@echo "    test-py              Run every Python package suite, report all failures (CI gate)"
	@echo "    test-all             Run all package tests (includes slow)"
	@echo "    test-pg              Real-Postgres tests (needs Docker or ZE_TEST_PG_URL); not part of test-py"
	@echo ""
	@echo "  Code quality"
	@echo "    check            Lint Python + ze-web build (CI lint gates)"
	@echo "    typecheck-web    Type-check ze-web and @myguyze/ze-ui (tsc --noEmit)"
	@echo "    hooks            Install git pre-commit / pre-push hooks"
	@echo "    lint             Lint all packages with ruff"
	@echo "    lint-web         Lint ze-web with ESLint (FSD boundaries)"
	@echo "    format           Auto-format and fix all packages with ruff"
	@echo "    deadcode         Dead-code report (vulture); report only, not a gate"
	@echo "    deadcode-tests-only  Definitions only tests reference"
	@echo "    test-scripts     Run scripts/ tests (graphify_reexports)"
	@echo "    clean            Remove __pycache__, .pytest_cache, .ruff_cache, *.pyc"
	@echo ""
	@echo "  Code generation"
	@echo "    codegen              Regenerate @myguyze/ze-client and @myguyze/ze-ui artifacts"
	@echo ""
	@echo "  Docker"
	@echo "    docker-up        Start all services via docker-compose"
	@echo "    docker-down      Stop all services"
	@echo "    docker-build     Build all Docker images"
	@echo ""

# ── Setup ─────────────────────────────────────────────────────────────────────
.PHONY: install web-install google-auth generate-ze-api-key

install:
	uv sync
	@echo "Tip: run 'make hooks' to install git pre-commit / pre-push quality gates"

web-install:
	bun install

google-auth:
	uv run python scripts/google_auth.py

generate-ze-api-key:
	uv run python $(ZE)/scripts/generate_ze_api_key.py $(if $(ZE_API_TOKEN),--token $(ZE_API_TOKEN))

# ── Database ──────────────────────────────────────────────────────────────────
.PHONY: db-up db-down db-reset reset-personal-state migrate migrate-down migrate-status migrate-history migrate-stamp

db-up:
	docker compose up -d postgres
	@echo "Waiting for Postgres to be ready..."
	@until docker compose exec -T postgres pg_isready -U ze -q; do sleep 1; done
	@echo "Postgres is ready."

db-down:
	docker compose stop postgres

# ── Workspace sidecar ─────────────────────────────────────────────────────────
.PHONY: workspace-up workspace-down

workspace-up:
	docker compose up -d workspace
	@echo "Waiting for the workspace sidecar to be ready..."
	@until curl -sf http://localhost:8081/health >/dev/null 2>&1; do sleep 1; done
	@echo "Workspace sidecar is ready on :8081."

workspace-down:
	docker compose stop workspace

db-reset:
	docker compose exec -T postgres psql -U ze -d postgres -c "DROP DATABASE IF EXISTS $(DB_NAME)"
	docker compose exec -T postgres psql -U ze -d postgres -c "CREATE DATABASE $(DB_NAME)"
	$(ZE_MIGRATE) upgrade

reset-personal-state:
	@if [ "$(CONFIRM)" != "RESET" ]; then \
		echo "Refusing to reset. Re-run with CONFIRM=RESET"; \
		exit 1; \
	fi
	uv run python scripts/reset_personal_state.py --scope personal_state --confirm RESET

migrate:
	$(ZE_MIGRATE) upgrade

migrate-down:
	$(ZE_MIGRATE) downgrade -1

migrate-status:
	$(ZE_MIGRATE) current

migrate-history:
	$(ZE_MIGRATE) history

# Stamp existing DB at all current heads after migration restructure.
# Run once on existing DBs that were on the old ze001–ze014 layout.
migrate-stamp:
	$(ZE_MIGRATE) stamp --purge zc018 zn002 zm008 zo001 zcor001 zcal001 zpros001 zpro001 zi001 zfin002

# ── Development ───────────────────────────────────────────────────────────────
.PHONY: dev web dev-full dev-eval logs seed db-reset-seed

dev: workspace-up
	uv sync -q --package ze-api
	ZE_PROFILE=$(ZE_PROFILE) AUTO_MIGRATE=true AUTO_SEED_DEV_DATA=true LOG_DEV=true LOG_FILE=$(LOG_FILE) uv run --package ze-api uvicorn ze_api.main:app --reload --host 0.0.0.0 --port 8000

web:
	cd $(ZE_WEB) && bun run dev

# Starts the backend in the background, waits for :8000 to be ready, then starts
# the React web app. Ctrl-C stops both.
dev-full: workspace-up
	@trap 'kill %1 2>/dev/null; exit 0' INT TERM; \
	uv sync -q --package ze-api; \
	ZE_PROFILE=$(ZE_PROFILE) AUTO_MIGRATE=true AUTO_SEED_DEV_DATA=true LOG_DEV=true LOG_FILE=$(LOG_FILE) uv run --package ze-api uvicorn ze_api.main:app --reload --host 0.0.0.0 --port 8000 & \
	until nc -z localhost 8000 2>/dev/null; do sleep 1; done; \
	echo "Backend ready — starting React web app..."; \
	cd $(ZE_WEB) && bun run dev; \
	kill %1 2>/dev/null

dev-eval:
	uv sync -q --package ze-api
	ZE_PROFILE=$(ZE_PROFILE) AUTO_MIGRATE=true EVAL_MODE=true PUBLIC_URL= LOG_DEV=true LOG_FILE=$(LOG_FILE) uv run --package ze-api uvicorn ze_api.main:app --reload --host 0.0.0.0 --port 8000

logs:
	tail -f $(LOG_FILE)

seed:
	cd $(ZE) && uv sync -q --package ze-api && AUTO_SEED_DEV_DATA=true uv run --package ze-api python -m ze_api.cli.seed apply

db-reset-seed: db-reset
	cd $(ZE) && uv sync -q --package ze-api && AUTO_SEED_DEV_DATA=true uv run --package ze-api python -m ze_api.cli.seed apply

# ── Eval ──────────────────────────────────────────────────────────────────────
.PHONY: eval eval-judge eval-report eval-diff eval-server eval-clean calibrate-commitment-intake calibrate-routing calibrate-skills calibrate-loop-gate calibrate-corroboration calibrate-complexity calibrate-open-query

eval:
	uv run python eval/run.py

eval-judge:
	uv run python eval/run.py --judge

eval-report:
	uv run python eval/run.py report

eval-diff:
	uv run python eval/run.py report --compare

eval-server:
	uv run python eval/server.py

calibrate-commitment-intake:
	uv run python eval/calibration/commitment_intake.py $(ARGS)

calibrate-routing:
	uv run python eval/calibration/routing.py $(ARGS)

calibrate-skills:
	uv run python eval/calibration/skills.py

calibrate-loop-gate:
	uv run python eval/calibration/loop_gate.py

calibrate-corroboration:
	uv run python eval/calibration/corroboration.py

calibrate-complexity:
	uv run python eval/calibration/complexity.py $(ARGS)

calibrate-open-query:
	uv run python eval/calibration/open_query.py $(ARGS)

eval-clean:
	@echo "Removing eval-namespaced rows from routing_log, checkpoints, llm_cost_log..."
	docker compose exec -T postgres psql -U ze -d $(DB_NAME) -c \
		"DELETE FROM routing_log WHERE session_id LIKE 'eval-%';"
	docker compose exec -T postgres psql -U ze -d $(DB_NAME) -c \
		"DELETE FROM llm_cost_log WHERE session_id LIKE 'eval-%';"
	docker compose exec -T postgres psql -U ze -d $(DB_NAME) -c \
		"DELETE FROM checkpoint_blobs WHERE thread_id LIKE 'eval-%';"
	docker compose exec -T postgres psql -U ze -d $(DB_NAME) -c \
		"DELETE FROM checkpoint_writes WHERE thread_id LIKE 'eval-%';"
	docker compose exec -T postgres psql -U ze -d $(DB_NAME) -c \
		"DELETE FROM checkpoints WHERE thread_id LIKE 'eval-%';"
	@echo "Removing eval fixture rows (update these when eval fixtures change)..."
	docker compose exec -T postgres psql -U ze -d $(DB_NAME) -c \
		"DELETE FROM user_reminders WHERE label ILIKE '%dentist%' OR label ILIKE '%build pipeline%' OR label ILIKE '%vitamins%';"
	docker compose exec -T postgres psql -U ze -d $(DB_NAME) -c \
		"DELETE FROM workflows WHERE description ILIKE '%email%digest%' OR description ILIKE '%calendar%briefing%';"
	docker compose exec -T postgres psql -U ze -d $(DB_NAME) -c \
		"DELETE FROM goals WHERE objective ILIKE '%books%' OR objective ILIKE '%rust%' OR objective ILIKE '%cli%';"
	docker compose exec -T postgres psql -U ze -d $(DB_NAME) -c \
		"DELETE FROM memory_facts WHERE value ILIKE '%dark mode%' OR value ILIKE '%rust%';"
	docker compose exec -T postgres psql -U ze -d $(DB_NAME) -c \
		"DELETE FROM contacts WHERE name ILIKE '%pedro%' OR name ILIKE '%maria%';"

# ── Testing ───────────────────────────────────────────────────────────────────
# Convention: make test-<short-name> from repo root. See docs/testing.md.
PYTEST      := uv run pytest
PYTEST_SLOW := $(PYTEST) -q
PYTEST_FAST := $(PYTEST) -m 'not slow' -q
pytest_pkg  = $(if $(SLOW),$(PYTEST_SLOW),$(PYTEST_FAST)) $(1)

# Ordered list for test-all (core → integrations → plugins → apps)
TEST_PY_PACKAGES := \
	test-logging \
	test-agents \
	test-communication \
	test-plugin \
	test-sdk \
	test-proactive \
	test-memory \
	test-onboarding \
	test-seed \
	test-correlation \
	test-browser \
	test-notifications \
	test-components \
	test-eval \
	test-google \
	test-trading212 \
	test-yt \
	test-ingestion \
	test-automation \
	test-worldstate \
	test-priority \
	test-skills \
	test-workspace \
	test-workspace-sidecar \
	test-collision \
	test-core \
	test-personal \
	test-messenger \
	test-calendar \
	test-prospecting \
	test-news \
	test-finance \
	test-scripts \
	test-api

.PHONY: test test-api test-core test-logging test-agents test-communication test-plugin test-sdk test-proactive \
	test-memory test-onboarding test-seed test-correlation test-browser test-notifications \
	test-components test-eval test-google test-trading212 test-yt test-ingestion test-automation test-worldstate test-priority test-skills test-workspace test-collision test-personal test-prospecting test-messenger \
	test-calendar test-news test-finance test-workspace-sidecar test-py test-all test-pg test-web web-test

test test-api:
	$(call pytest_pkg,apps/ze-api/tests)

test-core:
	$(call pytest_pkg,core/engine/ze-core/tests)

test-logging:
	$(call pytest_pkg,core/kernel/ze-logging/tests)

test-agents:
	$(call pytest_pkg,core/contracts/ze-agents/tests)

test-plugin:
	$(call pytest_pkg,core/contracts/ze-plugin/tests)

test-sdk:
	$(call pytest_pkg,packages/ze-sdk/tests)

test-proactive:
	$(call pytest_pkg,core/contracts/ze-proactive/tests)

test-memory:
	$(call pytest_pkg,core/cognition/ze-memory/tests)

test-ingestion:
	$(call pytest_pkg,core/ops/ze-ingestion/tests)

test-automation:
	$(call pytest_pkg,core/automation/ze-automation/tests)

test-worldstate:
	$(call pytest_pkg,core/cognition/ze-worldstate/tests)

test-priority:
	$(call pytest_pkg,core/arbitration/ze-priority/tests)

test-skills:
	$(call pytest_pkg,core/automation/ze-skills/tests)

test-workspace:
	$(call pytest_pkg,core/ops/ze-workspace/tests)

test-collision:
	$(call pytest_pkg,core/seam/ze-collision/tests)

test-onboarding:
	$(call pytest_pkg,core/ops/ze-onboarding/tests)

test-seed:
	$(call pytest_pkg,core/ops/ze-seed/tests)

test-correlation:
	$(call pytest_pkg,core/cognition/ze-correlation/tests)

test-browser:
	$(call pytest_pkg,integrations/ze-browser/tests)

test-notifications:
	$(call pytest_pkg,integrations/ze-notifications/tests)

test-components:
	$(call pytest_pkg,core/kernel/ze-components/tests)

test-eval:
	$(call pytest_pkg,core/ops/ze-eval/tests)

test-google:
	$(call pytest_pkg,integrations/ze-google/tests)

test-trading212:
	$(call pytest_pkg,integrations/ze-trading212/tests)

test-yt:
	$(call pytest_pkg,integrations/ze-yt/tests)

test-personal:
	$(call pytest_pkg,plugins/ze-personal/tests)

test-prospecting:
	$(call pytest_pkg,plugins/ze-prospecting/tests)

test-communication:
	$(call pytest_pkg,core/contracts/ze-communication/tests)

test-messenger:
	$(call pytest_pkg,plugins/ze-messenger/tests)

test-calendar:
	$(call pytest_pkg,plugins/ze-calendar/tests)

test-news:
	$(call pytest_pkg,plugins/ze-news/tests)

test-finance:
	$(call pytest_pkg,plugins/ze-finance/tests)

# The sidecar is not a uv workspace member; layer its own requirements on the venv.
test-workspace-sidecar:
	$(subst uv run,uv run --with-requirements sidecar/workspace/requirements.txt,$(call pytest_pkg,sidecar/workspace/tests))

# Runs every suite even when one fails, then exits non-zero naming the failures.
test-py:
	@failed=""; \
	for t in $(TEST_PY_PACKAGES); do \
		[ -n "$$GITHUB_ACTIONS" ] && echo "::group::$$t"; \
		$(MAKE) --no-print-directory $$t || failed="$$failed $$t"; \
		[ -n "$$GITHUB_ACTIONS" ] && echo "::endgroup::"; \
	done; \
	if [ -n "$$failed" ]; then echo "FAILED:$$failed"; exit 1; fi

test-all:
	@rc=0; $(MAKE) SLOW=1 test-py || rc=1; $(MAKE) test-web || rc=1; exit $$rc

test-pg:
	ZE_TEST_PG=1 uv run pytest -q -m pg apps/ze-api/tests/pg

test-web web-test:
	cd packages/ze-ui && bun run test
	cd $(ZE_WEB) && bun run test

# ── Web app build ─────────────────────────────────────────────────────────────
.PHONY: web-build

web-build:
	cd $(ZE_WEB) && bun run build

# ── Code generation ───────────────────────────────────────────────────────────
.PHONY: codegen

codegen:
	bun run scripts/codegen.ts

# ── Code quality ──────────────────────────────────────────────────────────────
.PHONY: check hooks process-install-hooks process-ready process-land-preflight process-gates process-review-request process-review-verdict lint lint-web typecheck-web format clean

check: lint web-build
	@echo "check: ok"

hooks:
	@chmod +x scripts/install-git-hooks.sh scripts/git-hooks/pre-commit scripts/git-hooks/pre-push
	@./scripts/install-git-hooks.sh

# Same hooks, plus the process checks that run only inside a Maestri terminal.
process-install-hooks: hooks
	@chmod +x scripts/process/precommit_checks.sh scripts/process/hooks/*.py

# Gates for the diff, hard checks, one receipt for HEAD in .process/receipts/.
# make process-ready [PORTAL_SHOT=<png>] [FLOOR=<name> sets the floor to review when green]
process-ready:
	@python3 scripts/process/ready.py $(if $(PORTAL_SHOT),--portal-shot $(PORTAL_SHOT)) $(if $(FLOOR),--set-review "$(FLOOR)")

# Refuse to land a floor that is not ready: make process-land-preflight [FLOOR=<path>]
process-land-preflight:
	@python3 scripts/process/land_preflight.py $(if $(FLOOR),--floor "$(FLOOR)")

# Full gate set with a receipt for HEAD (Ground, after the floor landed): make process-gates PROFILE=land
process-gates:
	@python3 scripts/process/ready.py --profile $(or $(PROFILE),diff)

# Review as files: make process-review-request RANGE=a..b REVIEWER=<name> [REQUESTER="Claude Code"]
process-review-request:
	@python3 scripts/process/review.py request "$(RANGE)" "$(REVIEWER)" $(if $(REQUESTER),--requester "$(REQUESTER)")

# make process-review-verdict RANGE=a..b VERDICT=APPROVE|CHANGES [FINDINGS=<file>]
process-review-verdict:
	@python3 scripts/process/review.py verdict "$(RANGE)" "$(VERDICT)" $(if $(FINDINGS),--findings "$(FINDINGS)")

lint:
	uv run ruff check .

lint-web:
	cd $(ZE_WEB) && bun run lint

typecheck-web:
	@rc=0; \
	(cd $(ZE_WEB) && bun x tsc --noEmit -p tsconfig.json) || rc=1; \
	(cd packages/ze-ui && bun x tsc --noEmit -p tsconfig.json) || rc=1; \
	exit $$rc

format:
	uv run ruff format .
	uv run ruff check --fix .

# ── Dead-code report (report only, never a gate) ──────────────────────────────
# `make deadcode` lists definitions nothing references (tests count as callers).
# `make deadcode-tests-only` lists definitions only tests reference.
# Needs `uvx` (uv) and network on the first run. Triage rules: specs/arch/cleanup-report-2026-10.md §1 and §10.
.PHONY: deadcode deadcode-tests-only test-scripts

VULTURE         := uvx vulture@2.16
VULTURE_PATHS   := core packages plugins integrations apps/ze-api eval scripts sidecar
VULTURE_SKIP    := */migrations/*,*/node_modules/*,*/.venv/*,*/generated/*
VULTURE_FLAGS   := --min-confidence 60 --ignore-decorators "@tool,@agent,@render_tool,@mcp.tool,@proactive_job,@pytest.fixture,@pytest_asyncio.fixture,@router.*,@app.*,@field_validator,@model_validator,@abstractmethod"
# Dropped hits: test files (they only supply references), plus variables that frameworks
# read by name: Pydantic response models under api/, LangGraph state keys, component descriptors.
# Also dropped: "unreachable code after 'raise'" (the `raise NotImplementedError` + `yield` async-generator stub idiom).
VULTURE_NOT_TESTS := ^[^:]*(/tests?/|/conftest\.py)
VULTURE_NOISE   := ^(apps/ze-api/ze_api/api/|plugins/[^/]+/[^/]+/api/|core/kernel/ze-components/ze_components/|core/engine/ze-core/ze_core/orchestration/state\.py|plugins/ze-personal/ze_personal/graph/workflow\.py)[^:]*:[0-9]+: unused variable
# vulture exits 3 when it finds dead code and 1 on a real error.
VULTURE_CHECK    = rc=$$?; if [ $$rc -ne 0 ] && [ $$rc -ne 3 ]; then echo "vulture failed ($$rc)" >&2; exit $$rc; fi

deadcode:
	@tmp=$$(mktemp); trap 'rm -f $$tmp $$tmp.clean' EXIT; \
	$(VULTURE) $(VULTURE_PATHS) $(VULTURE_FLAGS) --exclude "$(VULTURE_SKIP)" > $$tmp; $(VULTURE_CHECK); \
	grep -vE '$(VULTURE_NOT_TESTS)' $$tmp | grep -vE '$(VULTURE_NOISE)' | grep -v "unreachable code after 'raise'" | sort > $$tmp.clean; \
	echo "== Functions, methods, classes, properties (no reference anywhere)"; \
	grep -vE "unused (variable|attribute) " $$tmp.clean; \
	echo; echo "== Constants, fields, enum members (check stored values before deleting: report §10)"; \
	grep -E "unused (variable|attribute) " $$tmp.clean; \
	echo; echo "$$(wc -l < $$tmp.clean | tr -d ' ') hits. Report only: whitelist false positives in scripts/vulture_whitelist.py."

deadcode-tests-only:
	@a=$$(mktemp); b=$$(mktemp); trap 'rm -f $$a $$b $$a.s $$b.s' EXIT; \
	$(VULTURE) $(VULTURE_PATHS) $(VULTURE_FLAGS) --exclude "$(VULTURE_SKIP)" > $$a; $(VULTURE_CHECK); \
	$(VULTURE) $(VULTURE_PATHS) $(VULTURE_FLAGS) --exclude "$(VULTURE_SKIP),*/tests/*,*/conftest.py" > $$b; $(VULTURE_CHECK); \
	grep -vE '$(VULTURE_NOT_TESTS)' $$a | grep -vE '$(VULTURE_NOISE)' | grep -v "unreachable code after 'raise'" | sort > $$a.s; \
	grep -vE '$(VULTURE_NOISE)' $$b | grep -v "unreachable code after 'raise'" | sort > $$b.s; \
	echo "== Reached only from tests (wire it or delete it with its tests)"; \
	comm -13 $$a.s $$b.s

test-scripts:
	$(call pytest_pkg,scripts/tests)

clean:
	find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name '.pytest_cache' -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name '.ruff_cache' -exec rm -rf {} + 2>/dev/null || true
	find . -name '*.pyc' -delete 2>/dev/null || true

# ── Docker ────────────────────────────────────────────────────────────────────
.PHONY: docker-up docker-down docker-build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-build:
	docker compose build
