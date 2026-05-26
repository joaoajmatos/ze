# Ze Core — Alignment Gaps

Temporary working document. Delete once all items are resolved.

---

## 1. ~~Database Schema~~ ✓ DONE

Alembic migration at `ze_core/migrations/versions/001_initial_schema.py`.
Programmatic runner at `ze_core/migrate.py`.

```bash
# manual
python -m ze_core.migrate upgrade head

# automatic at startup
ZC_AUTO_MIGRATE=true python ...
```

Install: `pip install 'ze-core[migrations]'` (adds alembic + psycopg2-binary).

---

## 2. `decompose` Node is a Stub (Blocker)

`ze_core/orchestration/nodes/routing.py` line 67:

```python
async def decompose(state: AgentState, config: dict) -> dict:
    return {}
```

Compound routing goes to this node but it does nothing — subtasks are never
populated, so compound agents always receive an empty task list.

`fallback.decompose()` already exists and produces the right `RoutingEnvelope`.
The node just needs to call it.

**Action:** Implement `decompose` to call `fallback.decompose()` using
`config["configurable"]["router"]._client` and the agent registry, then store
the result in `state["envelope"]`.

---

## 3. Tool Execution Path (Design Decision Required)

`@tool` registers async functions. `BaseAgent.tools` lists names. But there is
no mechanism in ze_core for an agent to actually invoke a registered tool during
`run()`.

Two options:

**Option A — Framework provides a `ToolAgent` base class** with a built-in
ReAct loop (LLM → tool call → result → LLM …). Agents that use tools subclass
`ToolAgent` instead of `BaseAgent`. Ze Core handles the loop; agents only
declare tools and instructions.

**Option B — Convention only** — ze_core declares `@tool` and the tools list
for validation purposes; each agent implements its own tool-calling logic in
`run()`. Ze Core provides `get_tool(name)` and `ToolSpec.func` so agents can
dispatch, but the loop is the agent's responsibility.

Option A is more ergonomic but adds significant complexity to ze_core.
Option B is the current implicit state; just needs to be documented clearly.

**Action:** Decide, then either implement `ToolAgent` or document Option B
explicitly in `BaseAgent`'s docstring.

---

## 4. Interface ↔ Graph Bridge (Design Decision Required)

`AppInterface` is defined and validated, but:

- `Container.from_config()` does not accept an interface.
- Nothing calls `interface.send()` after the graph completes.
- The confirmation flow (`draft_response` → `await_confirmation`) pauses the
  graph but nothing calls `interface.send_confirmation()` or
  `interface.confirm()` before the pause.

The application is expected to call `interface.send()` itself after
`graph.ainvoke()` returns, but this contract is implicit.

For the **inline confirmation style**, the application must:
1. Run `graph.ainvoke()` until the graph pauses at `await_confirmation`.
2. Read `state["agent_result"]` and call `interface.confirm()`.
3. Resume with `graph.ainvoke(None, config)`.

For the **async confirmation style** (Telegram-style):
1. Run graph until pause.
2. Call `interface.send_confirmation()`.
3. Receive callback from transport → write decision to state → resume graph.

Neither path is enforced or even suggested by the container today.

**Action:** Either (a) add an `interface` parameter to `Container.from_config()`
with `validate_interface()` called at startup, or (b) write a concise
`docs/interface-integration.md` documenting the contract so application authors
know what to implement. Validate the interface style regardless.

---

## 5. `LLMClient` Protocol / `OpenRouterClient` Mismatch

`LLMClient.complete()` signature (routing/types.py):

```python
async def complete(
    self, messages, model, system=None, temperature=0.3,
    max_tokens=None, response_format=None, **kwargs
) -> str: ...
```

`OpenRouterClient.complete()` (openrouter/client.py):

```python
async def complete(self, messages, model, max_tokens=None) -> str:
```

`OpenRouterClient` does not satisfy `LLMClient`. Any code that type-checks
against the Protocol will fail.

**Action:** Add `system`, `temperature`, `response_format`, `**kwargs` to
`OpenRouterClient.complete()` and pass them through to the API payload.

---

## 6. `ze_core/__init__.py` Has No Public API

Currently just a docstring. A consumer doing `from ze_core import Container`
gets an `ImportError`.

**Action:** Re-export the primary public surface:

```python
from ze_core.container import Container
from ze_core.orchestration import BaseAgent, agent
from ze_core.orchestration.tool import ToolAccess, tool
from ze_core.memory import MemoryStore, MemoryConsolidator
from ze_core.settings import Settings
from ze_core.openrouter.client import OpenRouterClient
```

---

## 7. `asyncpg.Pool` as DI Key Forces Agent Hard-Dep on asyncpg

The container adds `asyncpg.Pool: pool` to the dependency map. An agent that
needs DB access must annotate `__init__(self, pool: asyncpg.Pool)`, which
requires importing asyncpg in the agent module.

Ze Core has `dependencies = []`, so this creates an implicit hard dependency
that breaks `_resolve()` if asyncpg is not installed.

**Action:** Either (a) document asyncpg as a required runtime dependency and
add it to `pyproject.toml` extras, or (b) introduce a `DBPool` type alias /
Protocol in `ze_core` that agents annotate against, keeping asyncpg an
implementation detail of the container.

---

## 8. `py.typed` Marker Missing

Without `ze_core/py.typed`, mypy and pyright treat the package as untyped and
ignore all annotations.

**Action:** `touch ze_core/py.typed` and add `"include": ["ze_core/py.typed"]`
to hatch build config.

---

## Summary Table

| # | Item | Severity | Effort |
|---|------|----------|--------|
| 1 | ~~Database schema (schema.sql / migration)~~ ✓ | Blocker | Small |
| 2 | `decompose` node is a stub | Blocker | Small |
| 3 | Tool execution path (design decision) | High | Medium–Large |
| 4 | Interface ↔ graph bridge (design decision) | High | Small–Medium |
| 5 | `OpenRouterClient` / `LLMClient` mismatch | Medium | Small |
| 6 | `ze_core/__init__.py` public API | Medium | Small |
| 7 | `asyncpg.Pool` DI key forces agent dep | Medium | Small |
| 8 | `py.typed` marker missing | Low | Trivial |
