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

## 2. ~~`decompose` Node is a Stub~~ ✓ DONE

Calls `fallback.decompose()` with the OpenRouter client, agent registry, and
fallback model from router config. Result stored in `state["envelope"]`.

---

## 3. ~~Tool Execution Path~~ ✓ DONE

`BaseAgent` now provides two methods agents can call from `run()`:

- **`call_tool(name, ctx, **kwargs)`** — capability-gated dispatch. Suppresses
  WRITE tools in DRAFT mode; raises `ToolBlockedError` in BLOCKED mode.
- **`agentic_loop(ctx, client, messages, system, deps, ...)`** — full ReAct loop.
  LLM picks tools, ze_core dispatches them, loop repeats until the model returns
  text. Falls back to a plain `complete()` call when `max_iterations` is reached.

Module-level helpers (`_merge_deps`, `_serialise_result`, `_truncate_messages`)
live in `base_agent.py` and are importable for testing.

The design mirrors Ze Phase 16: no separate `ToolAgent` subclass — the loop
lives directly on `BaseAgent` and agents opt in by calling it from `run()`.

---

## 4. ~~Interface ↔ Graph Bridge~~ ✓ DONE

`Container.from_config()` now accepts an optional `interface` parameter.
`validate_interface()` is called immediately at startup — misconfigured
interfaces fail fast before any DB or embedder initialisation.

Two new methods on `Container`:

- **`invoke(prompt, session_id, ...)`** — runs the full conversation turn.
  Checks `pending_confirmation` after the first graph pass and handles both
  confirmation styles:
  - *inline*: calls `interface.confirm()`, resumes graph on approval,
    calls `interface.send()` with the final response.
  - *async*: calls `interface.send_confirmation()`, returns
    `InvokeResult(confirmation_pending=True)`.
  - *no interface*: returns `InvokeResult(confirmation_pending=True)` so
    callers can handle the pause themselves.

- **`resume(session_id)`** — for async style; called after the transport
  callback writes the decision into state. Resumes the graph with
  `ainvoke(None, config)` and delivers the final response.

`InvokeResult(session_id, response, confirmation_pending, error)` added to
`interface/types.py` and exported from `ze_core.interface`.

---

## 5. ~~`LLMClient` Protocol / `OpenRouterClient` Mismatch~~ ✓ DONE

`OpenRouterClient.complete()` now accepts `system`, `temperature`,
`response_format`, `**kwargs` and passes them through to the API payload.

`complete_with_tools(messages, model, tools, system, temperature, max_tokens)`
added to both `OpenRouterClient` and the `LLMClient` Protocol.

---

## 6. ~~`ze_core/__init__.py` Has No Public API~~ ✓ DONE

Re-exports `Container`, `DBPool`, `BaseAgent`, `agent`, `ToolAccess`, `tool`,
`MemoryStore`, `MemoryConsolidator`, `OpenRouterClient`, `Settings`.

---

## 7. ~~`asyncpg.Pool` as DI Key Forces Agent Hard-Dep on asyncpg~~ ✓ DONE

`ze_core/db.py` introduces a `DBPool` Protocol. The container registers the
real pool under `DBPool` as the DI key. Agents annotate `pool: DBPool` without
importing asyncpg.

---

## 8. ~~`py.typed` Marker Missing~~ ✓ DONE

`ze_core/py.typed` created. Added `include = ["ze_core/py.typed"]` to hatch
build config in `pyproject.toml`.

---

## Summary Table

| # | Item | Severity | Effort |
|---|------|----------|--------|
| 1 | ~~Database schema (schema.sql / migration)~~ ✓ | Blocker | Small |
| 2 | ~~`decompose` node is a stub~~ ✓ | Blocker | Small |
| 3 | ~~Tool execution path~~ ✓ | High | Medium–Large |
| 4 | ~~Interface ↔ graph bridge~~ ✓ | High | Small–Medium |
| 5 | ~~`OpenRouterClient` / `LLMClient` mismatch~~ ✓ | Medium | Small |
| 6 | ~~`ze_core/__init__.py` public API~~ ✓ | Medium | Small |
| 7 | ~~`asyncpg.Pool` DI key forces agent dep~~ ✓ | Medium | Small |
| 8 | ~~`py.typed` marker missing~~ ✓ | Low | Trivial |
