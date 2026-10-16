# Implementation Plan: Retry Rollback

**Branch**: `180-retry-rollback` | **Date**: 2026-10-13 | **Spec**: [spec.md](spec.md)

## Summary

Retry gains rollback. Each REVERSIBLE WRITE tool returns a per-call **undo payload** when that call can be undone cleanly. `record_trace` stores it, with the owning agent and undo note, on `ToolCallTrace`. `retry_eligibility` turns a reversible-only latest reply into an **undo plan** (reverse call order, deterministic entry ids). The client confirms the plan; the WS `retry` frame carries the confirmed entry ids; the server recomputes the plan under the thread lock, refuses with `plan_changed` on mismatch, then runs a new **rollback executor** (`ze_core/conversation/rollback.py`). The executor calls each undo through the owning agent, stops at the first failure, persists a **rollback record** on the retried message (`messages.rollback`, `zc032`), and only then regenerates.

One retry policy replaces the 165 write block: irreversible writes are refused at dispatch, reversible writes run under normal gates, and a confirmation gate pauses the retry like a normal turn (the pending turn carries `retry_mode` and `retry_replaces`). ActionRecords written during an undo get the retried message id and a `supersedes` link via a `ze-agents` ContextVar read by `ActionRecorder`. `reprioritize_item` becomes reversible with a faithful restore. `remember_fact` returns the facts it displaced so its undo restores them.

## Technical Context

- **Languages**: Python 3.12 (FastAPI, LangGraph, asyncpg), TypeScript (React, `@myguyze/ze-client`, vitest).
- **Storage**: Postgres. One new nullable JSONB column `messages.rollback` (ze-core chain, `zc032`, revises `zc031`). No new tables. `priority_overrides`, `memory_facts`, `action_records` unchanged in shape.
- **Testing**: `make test-agents`, `test-core`, `test-memory`, `test-priority`, `test-worldstate`, `test-automation`, `test-calendar`, `test-personal`, `test-api`, `test-sdk`, `make test-web`, `make typecheck-web`. Mock asyncpg pools; no real OpenRouter. Eval scenarios updated and added.
- **Constraints**: pre-v1 hard cut (old traces have no payload → not undoable; the 165 all-writes-blocked retry rule is removed, not kept beside the new one); plugins use `ze_sdk` only; `ze-agents` must not import `ze_memory` or `ze_core`; `ze_core` is not imported by plugins.
- **Unknowns**: none left; see [research.md](research.md) R1–R9.

## Constitution / doctrine check

- **I Spec-first**: this spec, pinned scope, clarify session. ✅
- **II Single user**: consent is the person's own confirm; no roles. ✅
- **III Layered packages**: executor and eligibility in `ze-core`; payload contract and rollback ContextVar in `ze-agents` (re-exported by `ze-sdk`); per-domain payloads and undo paths in their owning packages; `ze-memory` reads the ContextVar from `ze-agents` (existing edge). No new package edges. ✅
- **IV Typed Python**: `UndoPlanEntry`, `RollbackRecord`, `RollbackEntry`, `RollbackScope` are dataclasses; Pydantic only in `ze_api/api/schemas.py`; new errors subclass `ZeError`. ✅
- **V Tests**: every FR maps to a test task; eval scenarios. ✅
- **VI Explicit persistence**: raw SQL Alembic `zc032`. ✅
- **VIII Pre-v1 hard cuts**: no payload backfill, one retry policy (C1), `retry_mode` semantics changed in place, removed reason codes deleted rather than aliased. ✅
- **Doctrine functions**: Action (undo is an action; ledger link), Governance (consent, plan guard, unknown never safe, no escalation), Perception (165 `retry_requested`, unchanged). Contribution seam: undos reuse each domain's existing write path; the priority restore reinstates an already-admitted override and submits no new claim (R6). ✅

## Package ownership

| Concern | Package | Files | Migration |
|---|---|---|---|
| `undo_payload` helper, `ToolCall.agent`/`ToolCall.undo`, rollback ContextVar, `BaseAgent.tool_deps()` + `run_undo()`, retry dispatch rule (block IRREVERSIBLE only) | `ze-agents` | `tool.py`, `types.py`, `rollback.py` (new), `base_agent.py`, `delegate.py` | none |
| SDK re-exports (`undo_payload`) | `ze-sdk` | `ze_sdk/__init__.py` | none |
| `ToolCallTrace.agent/undo_args/undo_note/call_index`, `MessageTrace.rollback`, eligibility + plan, rollback executor, retry turn with pause, `messages.rollback` store | `ze-core` | `conversation/{retry,rollback,turn}.py`, `conversation/messages/{types,store}.py`, `orchestration/nodes/{trace,execution}.py`, `migrations/versions/zc032_message_rollback.py` | `zc032` |
| ActionRecorder reads rollback scope (message id + supersedes) | `ze-memory` | `action_records/recorder.py` | none |
| `remember_fact` displaced ids; id-targeted retract + restore | `ze-memory` + `ze-personal` | `retriever.py`, `contribution.py`; `ze_personal/agents/companion/{tools,agent}.py` | none |
| `set_reminder` payload; reminders agent `tool_deps` | `ze-calendar` | `agents/reminders/{tools,agent}.py` | none |
| `create_goal`, `create_workflow`, `enable/disable_workflow` payloads; agents `tool_deps` | `ze-automation` | `agents/goals/{tools,agent}.py`, `agents/workflow/{tools,agent}.py` | none |
| `track_loop` payload (created only); loops agent `tool_deps` | `ze-worldstate` | `agents/{tools,agent}.py` | none |
| `reprioritize_item` REVERSIBLE + `restore_priority_override` undo tool; store `restore()`; `create()` returns superseded id | `ze-priority` | `tools.py`, `store.py`, `service.py`, `agent.py`, `errors.py` | none |
| WS retry frame `confirmed_plan`, refusal codes, plan in feedback view, pending-retry supersession on confirm/deny, rollback state in schemas | `ze-api` | `api/websocket/{turns,confirmation}.py`, `feedback_views.py`, `api/schemas.py`, `api/messages.py` | none |
| Two-step Retry, rollback notices, trace Rollback section | `ze-web` + `@myguyze/ze-client` | `features/retry-reply/*`, `features/reply-feedback/*`, `entities/message/*`, `widgets/trace-panel/*` | none |

## Design

### D1. Undo payload (per call)

A REVERSIBLE tool signals a clean undo by putting `"undo": undo_payload(**args)` in its normal result dict. `undo_payload` lives in `ze_agents.tool` and is re-exported as `ze_sdk.undo_payload`. `BaseAgent.call_tool` pops `"undo"` from a successful dict result of a REVERSIBLE tool into `ToolCall.undo`, so the model never sees it, and sets `ToolCall.agent = self.name` on every call. An `"undo"` key from a non-REVERSIBLE tool or a failed call is dropped and logged. Payload values must be JSON scalars or lists of scalars; `undo_payload` raises `AgentConfigError` otherwise. Per tool (R2–R6):

| Tool | Payload when | Payload | Undo tool |
|---|---|---|---|
| `set_reminder` | created | `{reminder_id}` | `cancel_reminder` |
| `create_goal` | created | `{goal_id}` | `abandon_goal` |
| `create_workflow` | created | `{workflow_name}` | `delete_workflow` |
| `enable_workflow` | was disabled | `{workflow_name}` | `disable_workflow` |
| `disable_workflow` | was enabled | `{workflow_name}` | `enable_workflow` |
| `remember_fact` | inserted | `{fact_id, restore_fact_ids}` | `forget_fact` (new id path) |
| `track_loop` | outcome `created` | `{loop_id}` | `drop_loop` |
| `reprioritize_item` | override written | `{override_id, prior_override_id}` (prior may be null) | `restore_priority_override` (new) |

`forget_fact` gains optional `fact_id` and `restore_fact_ids`. With `fact_id` it retracts that fact and un-contradicts `restore_fact_ids` in one transaction. It fails without change if the target fact is already contradicted or any restore id is not currently contradicted. Exactly one of `query` / `fact_id` is required; the model keeps using `query`.

### D2. Trace

`record_trace` copies `ToolCall.agent` and `ToolCall.undo` into `ToolCallTrace.agent` and `ToolCallTrace.undo_args`, copies `spec.undo_note` into `ToolCallTrace.undo_note`, and sets `ToolCallTrace.call_index` (position in the flattened list). Nested delegate calls keep the delegate agent's name because `call_tool` sets it. `MessageTrace` gains `rollback: RollbackTrace | None`, set on the regenerated reply (R8). Old trace rows parse with the new fields empty.

### D3. Eligibility and plan (`ze_core/conversation/retry.py`)

`retry_eligibility(message, trace, *, latest_assistant_id, thread_busy, pending, rollback)` where `rollback` is the retried message's stored `RollbackRecord | None`. Order:

1. not assistant → not applicable; pending → `turn_pending`; not latest → `not_latest`; busy → `busy`; no trace → `trace_unavailable`; unknown → `unknown_tool`; workspace → `workspace_run` (all as 165).
2. A rollback record with a `failed` entry → `undo_failed`, naming it.
3. Actions = writes that ran (`_is_action`), minus calls whose `call_index` the rollback record marks `undone`.
4. Any action IRREVERSIBLE → `confirmed_action` if its gate was approved, else `has_irreversible_action`.
5. Any action REVERSIBLE with `undo_args is None` → `not_undoable` ("… cannot be undone cleanly this time").
6. Otherwise available with `plan`: `UndoPlanEntry(entry_id, call_index, tool, undo_tool, agent, effect_phrase, undo_note, undo_args)` in reverse `call_index` order. An empty plan is a text-only retry.

`entry_id = sha256(f"{message.id}:{call_index}:{tool}:{canonical_json(undo_args)}")[:16]` (R7). Reason codes `has_reversible_action` and `has_write_action` are removed (no write is left without a class). `eligibility_payload` adds `plan` without `undo_args` and `agent`, which never leave the server.

### D4. Rollback executor (`ze_core/conversation/rollback.py`)

`async def run_rollback(plan, *, message_id, thread_id, message_store, session_id) -> RollbackRecord`. For each entry in order:

- `get_agent(entry.agent)`; a missing agent or an unregistered undo tool → `failed`.
- Inside `rollback_scope(RollbackScope(retried_message_id=message_id))` (ContextVar in `ze_agents/rollback.py`), call `agent.run_undo(entry.undo_tool, entry.undo_args, session_id=...)`.
- Success iff `ToolCall.success` and not `is_error_result(result)` (`{"error": …}`, `{"ok": False}`, `{"status": "error"}`).
- Record `undone` or `failed` with time and a sanitized failure code (no message content); mark the rest `not_attempted` after a failure.
- Persist `messages.rollback` after each entry so a crash leaves an honest record.
- Undos go through `call_tool`, so hooks and the Phase 144 constraint veto still apply (`cancel_reminder` has `constraint_gate=True`). A veto counts as a failed undo; do not bypass it.
- The retry runs in `_run_retry_task` (a background task), so a socket drop does not cancel it; its catch-all error text must reflect a stored rollback record.

`BaseAgent.run_undo(tool, args, *, session_id)` builds a minimal `AgentContext` (`gate_decision=EXECUTE`, `retry_mode=False`: the undo is the consented action, not part of the retry run), merges `self.tool_deps()`, and calls `self.call_tool(tool, ctx, **merged)`. The six owning agents move their inline `deps={…}` into `tool_deps()` and use it in their loop (no behavior change).

### D5. Retry turn

`handle_retry` (ze-api):

1. Validate the frame; load message, trace, rollback record; recompute eligibility and plan under the busy flag.
2. Non-empty plan: `confirmed_plan` missing → refuse `undo_not_confirmed`; not equal to the recomputed entry ids (same order) → refuse `plan_changed`. Nothing changes on refusal.
3. Append `retry_requested` (unchanged).
4. Non-empty plan: `run_rollback`. A `failed` entry → state `partial`, send `message_rollback` and an `error` frame with code `retry_partial`, stop.
5. `container.invoke_retry_turn(thread_id, text, replaces=old_id, …)`.
   - Completed → save the new reply with `replaces`, mark old superseded, set rollback state `superseded`, put the `RollbackTrace` on the new trace, send `message_superseded`.
   - Interrupted → no longer a failure. The handler sends the confirmation request; the pending config keeps `retry_mode` and `retry_replaces`. Rollback state becomes `rolled_back_awaiting_confirmation` (only when a rollback ran).
   - Failed or empty → restore history as today. If a rollback ran, state `rolled_back_retry_failed` and the `retry_failed` frame carries `rolled_back: true`.

`confirmation.py`: when the resolved pending config has `retry_replaces`, the produced reply (approve or deny) is saved with `replaces` and `after_save=mark_superseded`, the rollback state becomes `superseded`, and `message_superseded` is sent. If the resolution produces no reply (discarded on deny, or expired), the state becomes `rolled_back_retry_failed` (R5).

### D6. One retry policy

`BaseAgent.call_tool`: under `ctx.retry_mode`, refuse only tools whose `spec.reversibility is IRREVERSIBLE` (same `RETRY_WRITE_REFUSAL`, `gate="denied"`). `capability_check` (`execution.py`) and `delegate_to_agent` stop forcing `AWAIT_CONFIRMATION` / `DRAFT` to `EXECUTE` in retry mode, so gates behave as in a normal turn. `write_memory` still skips admission in retry mode. Text-only retries use the same path (C1).

### D7. Ledger link

`ActionRecorder.record_action` reads `current_rollback_scope()`. When set, `context = replace(context, message_id=scope.retried_message_id)` and `supersedes` = the id of the latest `succeeded` record for the same `authoritative_ref` with a different `action_type`, found through the existing `store.list(authoritative_ref=…)` call it already makes. A failed lookup leaves `supersedes=None`. Only `cancel_reminder` reaches this path today (R4).

### D8. Priority restore

`PostgresPriorityOverrideStore.create()` returns the id it superseded (`UPDATE … RETURNING id`); `submit_reprioritization` returns `(override, superseded_id)` and `reprioritize_item` puts both in its payload. New `restore(override_id, prior_override_id)` in one transaction:

- Fail with `StalePriorityRestoreError` unless `override_id` is still active (a later drag reorder or reprioritization superseded it).
- Set its `superseded_at = now()`.
- When `prior_override_id` is set and that row's `superseded_at` equals the new override's `submitted_at` (superseded by exactly this write), insert a copy with a new id and the prior's anchor, relation, pinned, `submitted_at` and `contribution_domain_id`.

New WRITE tool `restore_priority_override(override_id, prior_override_id=None)`, IRREVERSIBLE, `effect_phrase="restored an earlier priority order"`, on the priority agent. `reprioritize_item` becomes REVERSIBLE with `undo_tool="restore_priority_override"`, `undo_note="Restores the priority order from before this change"`. The clear-only fallback is not needed (R6).

### D9. Surfaces

- WS in: `retry` frame gains `confirmed_plan: list[str] | null`.
- WS out: `error` frame `code` gains `retry_partial`; `retry_failed` and `retry_partial` payloads gain `rolled_back: bool`. New frame `message_rollback` `{message_id, thread_id, rollback}` whenever the stored state changes.
- REST: `RetryEligibilityResponse` gains `plan: list[UndoPlanEntryResponse]`; `FeedbackView` and `MessageSchema` gain `rollback: RollbackRecordResponse | null`. Reason codes: add `not_undoable`, `undo_failed`, `plan_changed`, `undo_not_confirmed`; remove `has_reversible_action`, `has_write_action`. Details in [contracts/api.md](contracts/api.md). Client types regenerated (`make codegen`).
- Data portability: `messages.rollback` travels with the message row in export and import.

### D10. Web

- `features/retry-reply`: `RetryButton` becomes two-step when `plan.length > 0`. The first press opens an inline confirm region (`role="group"`, labelled list of `effect_phrase` + `undo_note`, Continue and Cancel, focus moves to Continue, Esc cancels). Continue sends the frame with `confirmed_plan`. An empty plan keeps one press.
- `useRetryReply`: handles `retry_partial`, `message_rollback`, and `retry_failed` with `rolled_back`; invalidates feedback, messages and trace queries.
- `features/reply-feedback` / `entities/message`: rollback notices on the retried reply for `partial`, `rolled_back_retry_failed`, `rolled_back_awaiting_confirmation` (`role="status"` text).
- `widgets/trace-panel`: `RollbackSection`. On the new reply: "Rolled back before this reply", entries, link to the replaced reply. On the retried reply: its stored record.

## Research / risks (see research.md)

R1 payload transport; R2 remember_fact displaced facts; R3 no-op detection for track_loop / enable / disable; R4 ActionRecord coverage; R5 pause/resume supersession and discard-on-deny; R6 priority restore without migration or new claim; R7 deterministic plan ids; R8 where the rollback record lives; R9 owning-agent dispatch outside the loop.

## Project structure (new/changed)

```
core/contracts/ze-agents/ze_agents/{tool.py,types.py,rollback.py,base_agent.py,delegate.py,__init__.py}
packages/ze-sdk/ze_sdk/__init__.py
core/engine/ze-core/ze_core/conversation/{retry.py,rollback.py,turn.py,__init__.py}
core/engine/ze-core/ze_core/conversation/messages/{types.py,store.py}
core/engine/ze-core/ze_core/orchestration/nodes/{trace.py,execution.py}
core/engine/ze-core/ze_core/migrations/versions/zc032_message_rollback.py
core/cognition/ze-memory/ze_memory/{retriever.py,contribution.py,action_records/recorder.py}
core/cognition/ze-worldstate/ze_worldstate/agents/{tools.py,agent.py}
core/automation/ze-automation/ze_automation/agents/{goals,workflow}/{tools.py,agent.py}
core/arbitration/ze-priority/ze_priority/{tools.py,store.py,service.py,agent.py,errors.py}
plugins/ze-calendar/ze_calendar/agents/reminders/{tools.py,agent.py}
plugins/ze-personal/ze_personal/agents/companion/{tools.py,agent.py}
apps/ze-api/ze_api/{feedback_views.py,api/schemas.py,api/messages.py,api/websocket/{turns,confirmation}.py}
apps/ze-web/src/{features/retry-reply,features/reply-feedback,entities/message,widgets/trace-panel}
eval/scenarios/{retry_rollback.yaml,retry_refused_after_write.yaml}
docs/{architecture.md,native-interface.md,adding-an-agent.md,data-portability.md}, AGENTS.md, specs/README.md,
specs/phases/165-response-feedback-retry/spec.md (Deferred section → link to 180)
```
