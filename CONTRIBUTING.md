# Contributing to Ze

Ze is a solo-maintained personal project. It is pre-v1, self-hosted, and in active development. Contributions are welcome, and the bar is practical: changes should be clean, tested, and easy to reason about. Before you build, read [VISION.md](VISION.md) and [AGENTS.md](AGENTS.md), which maps the repository. This guide takes you from zero to a merged PR.

---

## Getting started

**Prerequisites:** Python 3.12+, [uv](https://docs.astral.sh/uv/), Docker.

```bash
git clone https://github.com/joaoajmatos/ze.git
cd ze

make install       # install all packages in dev mode via uv
make db-up         # start Postgres (Docker)
make migrate       # apply all migrations

cp apps/ze-api/.env.example apps/ze-api/.env
# Fill in OPENROUTER_API_KEY, ZE_API_KEY, DATABASE_URL at minimum.

make dev           # API + WebSocket on :8000
make web-install   # React web app deps (Bun)
make web           # React web app on :5173
# or: make dev-full   # backend + web app together
```

---

## Workflow

1. **Fork** the repo and create a branch from `main`.
   Branch names: `feat/short-description`, `fix/short-description`, `chore/short-description`.

2. **Make your changes.** Keep each PR focused — one feature or fix per PR.

3. **Run checks** before pushing:
   ```bash
   make check       # ruff, ze-web ESLint (FSD boundaries) and ze-web tsc build — mirrors CI lint gates
   make test        # ze-api (skips slow) — must pass
   make test-web    # vitest — must pass if you changed ze-web
   make test-all    # optional, all packages including slow
   ```
   Install git hooks once so commits and pushes are checked automatically:
   ```bash
   make hooks       # pre-commit: staged ruff/tsc; pre-push: make check
   ```
   Bypass in an emergency: `SKIP=1 git commit` or `SKIP=1 git push`.
   Per-package targets: `make test-<name>` from repo root. Full list: [docs/testing.md](docs/testing.md).

4. **Open a PR** against `main`. The PR description should say *why* the change is needed,
   not just what it does.

5. We will not merge PRs that break tests or lint.

## Compatibility (pre-v1)

Ze is not at v1. Break APIs, schemas, and types when
the design is wrong. Do not add compatibility shims, deprecated aliases, or dual
write paths. Local databases may be wiped and remigrated. This default reverses
when a versioned v1 is declared. See
[specs/arch/pre-v1-hard-cuts.md](specs/arch/pre-v1-hard-cuts.md) and constitution
Principle VIII.

---

## Code conventions

These are enforced consistently across the codebase — please match them.

### Python

- **Domain types**: dataclasses in `types.py`. Never use Pydantic models outside `ze_api/api/schemas.py`.
- **File naming**: `types.py` everywhere (not `models.py`).
- **Dependency injection**: constructor injection in all classes. `FastAPI Depends()` only in `ze_api/api/`.
- **Logging**: `get_logger(__name__)` from structlog. No `print()`, no stdlib `logging`.
- **Errors**: subclass `ZeError` (from `ze_agents/errors.py` or `ze_api/errors.py`). Never raise bare `Exception` or `ValueError` in domain code.
- **LLM JSON**: parse every model reply with `parse_llm_json` (`ze_sdk`). Never call `json.loads` on model output.
- **Imports**: plugin code imports from `ze_sdk.*` only. Never import `ze_core` or `ze_plugin` from a plugin.
- **Async**: all I/O is async. Fire-and-forget via `asyncio.create_task()`. Never `asyncio.run()` inside a running loop.
- **Comments**: write none by default. Only add one when the *why* is non-obvious (a hidden constraint, a subtle invariant, a workaround for a specific external bug).

### Tests

- Tests live in `<package>/tests/` and mirror the package structure. Run a package with `make test-<name>`.
- `asyncio_mode = "auto"` — no `@pytest.mark.asyncio` needed.
- No real DB in unit tests — mock asyncpg pools with `AsyncMock`.
- No real LLM calls — mock `client.complete` and `client.stream`.
- Slow tests (embedding model load): mark with `@pytest.mark.slow`.
- Real-Postgres tests: mark with `@pytest.mark.pg`. Run them with `make test-pg`.

### Commits

Write commit messages in the imperative: **Add X**, **Fix Y**, **Remove Z**.
Keep the subject line under 72 characters. If the *why* isn't obvious from the diff, add a short body paragraph.

---

## Adding an agent

See [docs/adding-an-agent.md](docs/adding-an-agent.md) for the full authoring guide. The short version:

1. Write a spec first via spec-kit: `/speckit-specify` creates `specs/phases/NNN-<name>/spec.md`.
2. Create the agent in the owning plugin package under `agents/`, decorated with `@agent` and subclassing `BaseAgent`, both from `ze_sdk`.
3. Add the agent and tools modules to the plugin's `agent_module_paths()`, tools module first. No other wiring is needed.
4. Write tests in `tests/agents/<name>/`.

---

## Adding a database migration

Every package that owns tables owns its own Alembic chain. `ze_api/migrate.py` runs all the chains against one `alembic_version` table. [AGENTS.md](AGENTS.md#migration-ownership) lists each package, its prefix, and its tables.

1. Put the new file in the owning package's `migrations/versions/` directory, for example `core/cognition/ze-worldstate/ze_worldstate/migrations/versions/`.
2. Name it `{revision}_{feature}.py`, with the package prefix (for ze-worldstate, `zw`). The revision ID matches the file prefix. Never use a phase name.
3. Use `depends_on` when the migration needs a table from another package.
4. Run `make migrate`.

Never add plugin-owned tables to `ze-api` migrations. Migrations are raw SQL (no ORM). Keep them idempotent where possible.

---

## What not to send

- Changes to `.env` or any file containing secrets.
- New dependencies added without a clear reason — justify `uv add` changes to `pyproject.toml` in the PR description.
- Refactors unrelated to the stated goal of the PR.
- Comments that describe *what* the code does rather than *why*.

---

## Questions

Open a [GitHub issue](https://github.com/joaoajmatos/ze/issues) for bugs or feature requests.
For design questions, check `specs/` first — most decisions are already written up there.
