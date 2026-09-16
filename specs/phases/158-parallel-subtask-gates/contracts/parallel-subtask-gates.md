# Contract: Parallel subtask gates

Identifiers: `capability_check`, `_execute_compound`, `gate_decision`, `subtask_gate_decisions`, `request_id`, `GateDecision`, `run_delegate`.

## Routing into this contract

Applies only when `envelope.is_compound` is true **after** 153/155 rewrite (independent fan-out). Conductor envelopes (`is_compound` false, companion primary) MUST NOT use this partition.

## capability_check (compound)

| Subtask decisions | Graph next | Notes |
|---|---|---|
| All BLOCKED | END blocked | No execute |
| Any EXECUTE or DRAFT, any mix of AWAIT/BLOCKED | `execute_tool` | Do not `min()` to AWAIT |
| All AWAIT (no EXECUTE/DRAFT) | `execute_tool` still | Creates confirmations only; no specialist `run` yet |
| Single subtask | Today’s one `gate_decision` | FR-007; this table N/A |

Spend budget: compose per subtask as 152 (`min` of specialist decision vs AWAIT if over ceiling). Do not append one AWAIT onto the whole list then `min()`.

## execute_tool (compound)

- Gather EXECUTE (full) and DRAFT (draft mode) subtasks.
- For each AWAIT: no `run`; persist confirmation `request_id`; interrupt if any pending.
- Resume: run only the approved subtask as EXECUTE; leave other pending ids.
- Deny: that index contributes no success write; continue.
- Synthesize: `subtask_results` that actually completed; never claim denied/blocked success.

## Forbidden

- Restore `_execute_compound(..., is_sequential=True)` / `plan_sequential`.
- Change `run_delegate` / 152.
- Change `apply_conductor_rewrite`.
