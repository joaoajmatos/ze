# Contract: Edited Graph Nodes

Internal contracts — these are edits to two existing `ze_core.orchestration.nodes`
functions, not new nodes and not HTTP endpoints (research.md R1 — the spec originally
called for new standalone nodes; that was superseded after finding both mechanisms
already exist inside these two nodes). Documented here because they are the interface
tests are written against.

## `write_memory` — compaction branch

`core/ze-core/ze_core/orchestration/nodes/memory.py`

Existing signature, unchanged:

```python
async def write_memory(state: AgentState, config: RunnableConfig) -> dict:
    ...
```

**New behavior**, inserted immediately before the existing
`return {"messages": updated[-SESSION_HISTORY_LIMIT:]}` (line 116):

1. Estimate `updated`'s token count (chars/4 heuristic, research.md R4).
2. Resolve the routed model: `ctx.model or resolve_model("synthesis", MODEL_SYNTHESIS,
   app_config)` (mirrors the existing call at line 130).
3. Look up `get_context_window(model)` (new `ze_core.openrouter.context_windows`
   module).
4. If the estimate is under 70% of that window: unchanged — return
   `{"messages": updated[-SESSION_HISTORY_LIMIT:]}` exactly as today.
5. If at/over 70%: split `updated` at `-SESSION_HISTORY_LIMIT`; summarize the older
   span via `config["configurable"]["openrouter_client"]` with a new compaction prompt
   (distinct from `SessionSummariser._SUMMARY_SYSTEM`); on success, return
   `{"messages": [summary_message] + updated[-SESSION_HISTORY_LIMIT:]},
   "compaction_span": (0, len(older_span) - 1)}`; on LLM error/timeout, catch and fall
   back to step 4's behavior (research.md R7), still returning
   `"compaction_span": None`.

**Reads** (all already available in this node): `state["messages"]` (via `updated`,
built from `state.get("messages")` + this turn's new entries), `state.get("agent_context")`
for `ctx.model`, `config["configurable"]["openrouter_client"]`,
`config["configurable"]` app config (for `resolve_model`).

**Writes** (new): `compaction_span: tuple[int, int] | None` in the returned partial
state.

**Failure mode**: never raises out of the node for a summarization failure — falls back
to the pre-existing trim (FR-010).

## `fetch_context` — resume-recap branch

`core/ze-core/ze_core/orchestration/nodes/context.py`

Existing signature, unchanged:

```python
async def fetch_context(state: AgentState, config: RunnableConfig) -> dict:
    ...
```

**New behavior**, inside the existing gap-check branch (lines 64-66):

```python
if last_active and (now - last_active) > (inactivity_minutes * 60):
    history: list[dict] = []
    log.info("session_expired", session_id=state["session_id"])
    recap = await _assemble_resume_recap(state, config)  # NEW — returns ResumeRecap | None
else:
    history = list(state.get("messages") or [])
    recap = None
```

`history = []` is unchanged (compaction and resume-recap are independent — R2 vs R5;
this branch still starts the model-facing window fresh on a real gap, per the existing
design). What changes is that `agent_context.resume_recap` (new `AgentContext` field) is
set from `recap.render()` when `recap` is not `None` and has content (FR-008 — empty
when nothing outstanding), immediately after `agent_context` is constructed
(mirroring how `screen_context_note` is set at line 121).

**Reads** (new, inside `_assemble_resume_recap`): `config["configurable"]["memory_store"]`
(or the store exposing `get_session_summary`), `config["configurable"]["loop_surfacer"]`,
goal/workflow store handles from `config["configurable"]` (single-user — no thread
filter, research.md R5).

**Writes** (new): `agent_context.resume_recap: str | None`; `resume_recap_applied: bool`
added to this node's returned partial state dict for `record_trace` to pick up.

**No-op condition**: gap under threshold, or nothing outstanding — `resume_recap` stays
`None`, `resume_recap_applied = False` (FR-008, FR-009).

**Threshold**: uses the same `session_inactivity_minutes` config key `SessionSummariser`
reads — no new threshold constant is introduced (FR-006).
