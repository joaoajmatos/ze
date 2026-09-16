# Data model: Per-Delegate Gate

No new tables. Reuse `pending_confirmations`.

## Delegate evaluation input

| Field | Source |
|---|---|
| `agent` | `agent_name` |
| `intent` | Optional tool `intent`, else CapabilityGate default |
| `session_overrides` | Graph state, same as `capability_check` |
| spend | `SpendBudgetChecker.check(session_id)` when configured |

## Decision application

| Decision | Worker | Conductor |
|---|---|---|
| EXECUTE | `run` with EXECUTE | Continues after result |
| DRAFT | `run` with DRAFT | Continues after draft result |
| BLOCKED | No `run`; failed ToolCall | Continues (no confirm UI) |
| AWAIT_CONFIRMATION | No `run` until approve | Pause; persist `request_id` |

## Confirmation row (existing)

| Column | Use |
|---|---|
| `request_id` | Primary key (113) |
| `thread_id` | Session; not unique |
| payload | Specialist name, fat brief fields, intent |

On approve: that row’s invocation runs EXECUTE. Other `request_id`s on the thread remain.

## 151 fields (unchanged)

`agent_name`, `objective`, `prior_outputs`, `inputs`, `output_shape`, `stop_condition` plus optional `intent`.

## Deleted behavior

Parent `gate_decision` copied onto `AgentContext` for workers as the only gate.
