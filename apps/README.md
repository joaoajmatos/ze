# apps/

Runnable deployment units. These packages wire everything together. They import from
both `core/` and `plugins/`, and neither imports them.

Package READMEs follow [docs/package-readme-template.md](../docs/package-readme-template.md).
Tests run from the repo root via `make test-<short-name>`. See [docs/testing.md](../docs/testing.md).

---

## Packages

| Package | Description |
|---------|-------------|
| [ze-api](ze-api/) | FastAPI/WebSocket backend — HTTP API, WebSocket chat endpoint, background jobs, plugin wiring |
| [ze-web](ze-web/) | React web client (Vite + TypeScript + Tailwind + shadcn/ui) |

## ze-api

This package instantiates `ZeContainer` and registers all `ZePlugin`
implementations. No other package does. It owns:

- The WebSocket endpoint (`/ws`) and REST management routes
- `NativeAppInterface` — WebSocket + ntfy push delivery
- The Alembic meta-runner (`ze_api/cli/migrate.py`) that runs every package's migration chain. `ze-api` owns no tables.
- `config/config.yaml` and `config/persona.yaml`

```bash
make dev        # uvicorn --reload on :8000
make migrate    # apply pending migrations
make test       # run ze-api tests
make test-api   # same as test
```

## ze-web

React SPA. Connects to `ze-api` over WebSocket at `/ws`. It has no Python dependencies and runs on the Bun JavaScript runtime.

```bash
make web        # bun dev server on :5173
make web-build  # production build
make web-test   # vitest — alias for test-web
```

## Dependency graph

```
ze-api  ←  ze-core, ze-automation, ze-worldstate, ze-priority, ze-skills, ze-workspace,
            ze-collision, ze-data, ze-ingestion, ze-yt, ze-logging, ze-memory,
            ze-correlation, ze-personal, ze-messenger, ze-prospecting, ze-browser,
            ze-news, ze-finance, ze-notifications, ze-components, ze-onboarding,
            ze-calendar, ze-seed, ze-google, ze-agents, ze-communication, ze-plugin,
            ze-proactive
ze-web  ←  (React — connects to ze-api over WebSocket, no Python deps)
```

The authoritative list is the `dependencies` table in `ze-api/pyproject.toml`.
