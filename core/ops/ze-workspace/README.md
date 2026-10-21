# ze-workspace

Isolated durable workspace — files, shell, and scripting runtimes beside the mind.

## Role in Ze

Ze's agents need a computer: a place to write files, run commands, and execute approved skill scripts. That computer is a separate sidecar. This package is the Python client, gate, tools, and Postgres store that talk to it.

The sidecar is not a browsing session. Web pages stay in `ze-browser`. This package must not be imported by `ze-core` or `ze-agents`; `ze-api` wires it and merges the tools at runtime.

### Key features

- `WorkspaceClient` — async HTTP client for the sidecar
- `WorkspaceGate` — action × origin → allow, confirm, or deny
- `workspace_*` tools — list, read, write, delete, run, run skill script, ingest, reset
- Durable `workspace_state` and `workspace_runs` in Postgres, with a run journal that survives `ze-api` restarts
- Follow-through — a `RunWatcher` that watches detached runs, starts a follow-up turn, and pushes when the client is offline
- REST routes under `/api/v0/workspace`

### Integration

`ze-api` builds the stack, injects `WorkspaceClient` / `WorkspaceGate` / `WorkspaceStore`, and calls `workspace_tools.configure(...)`. `BaseAgent.agentic_loop` merges the workspace tool names in its `_PLATFORM_TOOLS` tuple. Unattended goal/workflow runs use a duck-typed gate in `ze-automation` so that package never imports `ze_workspace`.

![ze-workspace package dependencies](../../docs/diagrams/core/ops/ze-workspace/dependencies.svg)

<sub>[Interactive version](../../docs/diagrams/core/ops/ze-workspace/dependencies.html)</sub>

`screen_resolvers.py` registers `workspace_run` and the `workspace_placed` pseudo-ref, which names files the user placed this turn.

## Responsibilities

| Module | What it provides |
|---|---|
| `client.py` | `WorkspaceClient` — async HTTP client for the sidecar |
| `gate.py` | `WorkspaceGate` — action × origin decisions |
| `tools.py` | `workspace_*` `@tool`s |
| `store.py` | `workspace_state` and `workspace_runs` |
| `followthrough.py` | `RunWatcher` — watch detached runs, follow-up turn, push |
| `turn_lock.py` | Per-thread lock for follow-up turns |
| `action_records.py`, `action_handoff.py` | Action-record submissions for runs |
| `scripts.py` | `WorkspaceScriptRunner` — runs a tool script over the sidecar's `WS /scripts` and serves its tool calls |
| `script_learning.py` | `ScriptLearning` — one ledger row per script run; a procedure candidate after three straight successes |
| `rest.py` | FastAPI helpers: status, files, reset |
| `sanitize.py` | Path confinement and secret redaction |
| `types.py` | Action, origin, run, and file types |
| `errors.py` | `WorkspaceError` and subtypes |
| `bootstrap.py` | Container wiring helpers |

Every `WRITE` tool in this package declares `reversibility` and an `effect_phrase`. Retry reads these declarations to decide if a reply can be regenerated.

## Dependencies

`ze-agents`, `ze-logging`, `ze-data`, `ze-memory`, `ze-plugin`, `httpx`, `websockets`, `asyncpg`. `ze-core` and `ze-agents` must not depend on this package.

## Usage

The sidecar runs as a separate Docker service (`sidecar/workspace/`). Point Ze at it with `WORKSPACE_SERVICE_URL`.

```python
from ze_workspace.client import WorkspaceClient

client = WorkspaceClient(
    base_url="http://ze-workspace.internal:8080",
    token="...",
    timeout=120,
)
stat = await client.stat()
```

## Configuration

| Setting | Description |
|---|---|
| `WORKSPACE_SERVICE_URL` | URL of the workspace sidecar |
| `WORKSPACE_API_TOKEN` | Bearer token for the sidecar control API |
| `WORKSPACE_TIMEOUT_SECONDS` | Per-request HTTP timeout |
| `WORKSPACE_FOLLOW_THROUGH_SHORT_WAIT_SECONDS` | Seconds a turn waits for a command before it detaches |

`WorkspaceStack.script_runner` is set only when both `WORKSPACE_SERVICE_URL` and `WORKSPACE_API_TOKEN` are set, because the sidecar refuses `/scripts` without a token. The runner checks `GET /stat` first and never opens the socket when `scripts_isolated` is false.

See [docs/workspace.md](../../docs/workspace.md) for access, isolation, and local/Fly setup.
See [docs/skills.md](../../docs/skills.md) for how skill scripts reach this sidecar.

## Testing

From the repo root:

```bash
make test-workspace
```

See [docs/testing.md](../../docs/testing.md).
