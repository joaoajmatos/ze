# ze-logging

Structured logging for Ze — `structlog` configuration, context binding, and no-dependency access to `get_logger`.

## Role in Ze

Every package in the monorepo logs the same way: structured, JSON in production, colorized in development, with session and agent identifiers attached automatically rather than passed at every call site. `ze-logging` is the one place that configuration lives, so it has zero Ze dependencies and can sit under every other package without creating a cycle.

`get_logger(__name__)` is the only logging entry point allowed anywhere in the codebase — `print()` and the stdlib `logging` module are disallowed by convention (see the root `CLAUDE.md`).

### Key features

- `configure_logging()` — call once at process startup; JSON renderer in production, `ConsoleRenderer` in dev, optional tee to a log file
- `get_logger(name)` — returns a `structlog` bound logger
- `bind_context()` / `unbind_context()` — attach `session_id` / `agent` to every log line emitted in the current async context, without threading them through every function signature

### Integration

`ze-api` calls `configure_logging()` once during startup. Every other package imports `get_logger` directly — `ze-logging` has no Ze dependencies, so it is safe to import from `core/`, `plugins/`, `integrations/`, and `apps/` alike.

## Responsibilities

| Module | What it provides |
|---|---|
| `__init__.py` | `configure_logging`, `get_logger`, `bind_context`, `unbind_context`, `_TeeStream` |

## Dependencies

No Ze dependencies. Third-party: `structlog`.

## Usage

```python
from ze_logging import get_logger, bind_context

log = get_logger(__name__)

bind_context(session_id="abc123", agent="companion")
log.info("agent_turn_started")
```

## Testing

From the repo root:

```bash
make test-logging
```

See [docs/testing.md](../../docs/testing.md).
