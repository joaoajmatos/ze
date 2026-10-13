# Research: Retry Rollback

All findings verified against code on 2026-10-13 (main @801519a6 merged into the floor).

## R1. How a tool reports its undo payload

- **Decision**: The tool puts `"undo": undo_payload(...)` in its result dict; `BaseAgent.call_tool` pops it into `ToolCall.undo` for REVERSIBLE tools only.
- **Rationale**: The tool is the only code that knows whether this call created something new, was a no-op, or touched a pre-existing record. Popping keeps ids out of the model's tool message. No new tool signature or context object.
- **Alternatives**: A declarative `@tool(undo_args=...)` mapping cannot express no-op or existing-record outcomes (rejected at scope pin, Q1 B). Reading ids from the ActionRecord ledger fails for tools that write none (Q1 C, R4). A ContextVar side channel is invisible in tests and in the tool's return type.

## R2. `remember_fact` is not undone by retracting one fact

- **Finding**: `_write_fact_with_contradiction_check` (`ze_memory/retriever.py:828`) marks every live fact with the same predicate and subject `contradicted = true`, then runs `_apply_semantic_contradiction_check`, which can mark more. Retracting only the new fact would leave the earlier value hidden: memory would not read as before the turn.
- **Decision**: The write returns the ids it displaced (`UPDATE … RETURNING id`, plus the semantic check's ids). `submit_perception_facts` exposes them on the `Fact` (`fact.displaced_ids`). `remember_fact` puts `{fact_id, restore_fact_ids}` in its payload. The id path on `forget_fact` retracts the new fact and un-contradicts the displaced ones in one transaction, failing if any of them is no longer contradicted (something else changed it since).
- **Alternatives**: Payload only when nothing was displaced. Rejected: "my favourite colour is now blue" is the common case and would never be undoable.

## R3. No-op detection

- `track_loop` already returns `outcome` (`created|confirmed|reinforced|revived`); payload only for `created`.
- `enable_workflow` / `disable_workflow` read `wf` before `set_enabled`; payload only when `wf.enabled` differed from the target.
- `set_reminder`, `create_goal` (returns `id`), `create_workflow` always create on success.
- `reprioritize_item` returns `no_op` / `clarification_needed` / `error` without writing; payload only on a written override.

## R4. ActionRecord coverage of in-scope tools

- **Finding**: Of the create and undo tools in scope, only reminders write ActionRecords (`ze_calendar/action_records.py` `emit_reminder_mutation`, called by `set_reminder` and `cancel_reminder`). `ze_automation/action_records.py` covers goal traces and workflow executions, not `create_goal` / `abandon_goal` / `create_workflow` / `delete_workflow` / enable / disable. Memory facts, loops, priority overrides write none.
- **Decision**: Per Q7 A, no new instrumentation. The ledger link (FR-022) is centralized in `ActionRecorder.record_action` via a rollback-scope ContextVar, so any producer that already records gets the message id and `supersedes` automatically, today `cancel_reminder`. The spec was corrected to say so.
- **Note**: `ActionRecorder` already calls `store.list(authoritative_ref=…)` for causal refs; the `supersedes` lookup reuses that result (no extra query).

## R5. Retry that pauses at a confirmation

- **Finding**: `invoke_retry_turn` treats `result.interrupted` as failure and restores history. Retry mode also forced gates to `EXECUTE` (`execution.py:133`, `:155`; `delegate.py:279`). The resume path (`api/websocket/confirmation.py`) saves the produced reply with `send_with_thread` and no `replaces`. On deny when the graph is not inside a node, the pending checkpoint is aborted and no reply is produced.
- **Decision**: The retry run keeps gates (D6). On interrupt, `invoke_retry_turn` returns the result; the handler sends the confirmation request. The retry identity travels in the pending config's `configurable` (`retry_mode`, `retry_replaces`), which `pending_confirmations` already persists with the request. `confirmation.py` checks `retry_replaces` and supersedes on any produced reply (C2). No reply → `rolled_back_retry_failed`, Retry available with an empty plan.

## R6. Priority restore

- **Finding**: `priority_overrides` is append-only with `superseded_at` (`zpri001`). `create()` supersedes the item's active override in the same transaction. The superseded row stays.
- **Decision**: Faithful restore without migration (D8): supersede the new row, re-insert a copy of the prior row keeping its `submitted_at` (decay timing) and `pinned`, only if that prior row was superseded by exactly this write (`superseded_at == new.submitted_at`). A later change (REST drag, another reprioritization) makes the new row inactive and the restore fails cleanly (FR-008).
- **Seam**: The restore submits no new contribution: it reinstates a claim the seam already admitted, and the reprioritization's own collision log stays as history. The new tool is IRREVERSIBLE and is only meant as an undo; its description says so.

## R7. Plan entry ids

- **Decision**: `sha256(message_id:call_index:tool:canonical_json(undo_args))[:16]`. Deterministic from the stored trace, so the client's confirmed list and the server's recomputed plan compare exactly; any change to the trace-derived plan or the rollback record (undone entries drop out) changes the list.

## R8. Where the rollback record lives

- **Decision**: `messages.rollback JSONB NULL` on the retried message (`zc032`). Eligibility needs it on every read of that message, it must survive the trace immutability rule from 165 (FR-009 there), and it must exist when no new reply exists (partial, retry failed). The new reply's `MessageTrace.rollback` is a copy for the trace panel.
- **Alternatives**: A new table (unneeded for one row per message), writing into the old trace (violates 165 FR-009).

## R9. Running an undo outside the model loop

- **Finding**: Tool dependencies are agent-private: each agent passes `deps={...}` to `agentic_loop` (reminders, goals, workflow, companion, loops, priority). `get_agent(name)` (`ze_agents.registry`) returns the instance used by `execute_tool`.
- **Decision**: `BaseAgent.tool_deps() -> dict` (default `{}`) and `BaseAgent.run_undo(tool, args, *, session_id)`, which calls `call_tool` so hooks, logging and constraint gates still apply. The six agents move their inline deps into `tool_deps()`. `ToolCall.agent` (set by `call_tool`) gives the trace the owning agent, including nested delegate calls.
