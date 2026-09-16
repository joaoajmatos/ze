# Data model: Conductor stall / replan

## Ledger statuses (153 closed set + additive)

`planned` | `running` | `done` | `awaiting_confirmation` | `denied` | `skipped` | `ask_user` | **`stalled`** | **`replanned`**

| Status | Meaning |
|---|---|
| `stalled` | Last invocation of that specialist produced no usable output |
| `replanned` | Engine-allowed silent retry was issued (brief updated) |
| `ask_user` | Cap or second stall; user must answer; no further delegates to the blocked target |

## Turn-local counters (not tables)

| Field | Type | Rule |
|---|---|---|
| `conductor_delegate_total` | int | Increment on each `delegate_to_agent` that starts a specialist; cap **6** |
| `conductor_delegate_counts` | map agent_name → int | Cap **2** per name (initial + one retry) |

Checkpoint with graph state so 152 resume does not reset the budget.

## Stall detector input

Tool result from `run_delegate`: error flag / empty `response`.
