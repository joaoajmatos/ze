# Data Model: Retry Rollback

## ToolCall (ze-agents, in memory) — changed
| Field | Type | Notes |
|---|---|---|
| `agent` | `str \| None` | set by `BaseAgent.call_tool` to `self.name` |
| `undo` | `dict[str, Any] \| None` | popped from a successful REVERSIBLE result's `"undo"` key |

## ToolCallTrace (ze-core, in `messages.trace` JSONB) — changed
| Field | Type | Notes |
|---|---|---|
| `agent` | `str \| None` | owning agent |
| `undo_args` | `dict \| None` | payload; ids and names only; never sent to clients |
| `undo_note` | `str \| None` | copied from the declaration at record time |
| `call_index` | `int` | position in the flattened call list, from 0 |

## UndoPlanEntry (ze-core `retry.py`, derived)
`entry_id: str` (R7), `call_index: int`, `tool: str`, `undo_tool: str`, `agent: str`, `effect_phrase: str`, `undo_note: str`, `undo_args: dict`. Plan = entries in reverse `call_index`. Public projection drops `agent` and `undo_args`.

## RetryEligibility (ze-core) — changed
Adds `plan: list[UndoPlanEntry]` (empty when available text-only or unavailable). Reason codes: `not_latest`, `confirmed_action`, `has_irreversible_action`, `not_undoable` (new), `undo_failed` (new), `workspace_run`, `trace_unavailable`, `unknown_tool`, `turn_pending`, `busy`, `disconnected` (client). Request-time refusals (not eligibility): `plan_changed`, `undo_not_confirmed`. Removed: `has_reversible_action`, `has_write_action`.

## RollbackRecord (ze-core, `messages.rollback` JSONB on the retried message) — new
| Field | Type | Notes |
|---|---|---|
| `state` | `"partial" \| "rolled_back_awaiting_confirmation" \| "rolled_back_retry_failed" \| "superseded"` | |
| `entries` | `list[RollbackEntry]` | plan order |
| `started_at` / `updated_at` | ISO timestamps | |
| `replaced_by` | `UUID \| None` | mirrors `messages.replaced_by` when superseded |

RollbackEntry: `entry_id`, `call_index`, `tool`, `undo_tool`, `effect_phrase`, `outcome: "undone" | "failed" | "not_attempted"`, `at`, `failure_code: str | None` (sanitized, no content).

State transitions (only while rollback ran; text-only retries write no record):
```
(none) ──all undone──▶ regenerate ─ok──────────────▶ superseded
                         ├─interrupt──▶ rolled_back_awaiting_confirmation ─reply─▶ superseded
                         │                                                 └no reply▶ rolled_back_retry_failed
                         └─fail────────▶ rolled_back_retry_failed ─(text-only retry ok)─▶ superseded
(none) ──an undo failed──▶ partial   (eligibility → undo_failed; terminal in this phase)
```

## RollbackTrace (ze-core, on the regenerated reply's `MessageTrace.rollback`) — new
`replaces: UUID`, `entries: list[RollbackEntry]` (the undone ones).

## RollbackScope (ze-agents `rollback.py`, ContextVar) — new
`retried_message_id: UUID`. Read by `ze_memory.action_records.ActionRecorder`.

## Migration `zc032_message_rollback` (ze-core chain, revises `zc031`)
`ALTER TABLE messages ADD COLUMN IF NOT EXISTS rollback JSONB NULL`; downgrade drops it. No index (read by message id).

## PriorityOverride store (ze-priority) — behavior only
`create()` also returns the superseded id; new `restore(override_id, prior_override_id)`. No schema change.

## Memory facts (ze-memory) — behavior only
Fact write returns displaced ids; new id-targeted retract-and-restore. No schema change.
