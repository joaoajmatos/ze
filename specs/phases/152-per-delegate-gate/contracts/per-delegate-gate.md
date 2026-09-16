# Contract: Per-delegate `run_delegate` gate

Identifiers: `run_delegate`, `gate_decision`, `CapabilityGate`, `request_id`, optional `intent`, `delegate_to_agent`, `AWAIT_CONFIRMATION`, `EXECUTE`, `DRAFT`, `BLOCKED`, Principle VIII.

## Evaluation (normative)

```text
specialist_decision = CapabilityGate.evaluate(agent_name, intent, session_overrides)
if spend over ceiling: specialist_decision = min(specialist_decision, AWAIT_CONFIRMATION)
worker.gate_decision = specialist_decision
# parent companion gate_decision MUST NOT be assigned as worker.gate_decision
```

`intent` = tool argument if present else existing CapabilityGate missing-intent default.

## Schema delta vs 151

Add optional property `intent`. Do not remove 151 properties. `task`/`context` stay gone.

## Confirmation

| Event | Contract |
|---|---|
| Hold | No specialist `run`; row in `pending_confirmations` keyed by `request_id` |
| Approve | Same `request_id`; specialist `run` once with EXECUTE |
| Deny | No write; companion must not claim success |
| Sibling | Different `request_id` on same `thread_id` unaffected |

## Engine wiring

`ze_agents` sees a callback/protocol only. `ze_core` `execute_tool` supplies it. Tests may inject a fake evaluator.

## Out of contract

Graph `capability_check` strictest-wins for parallel compound. `plan_sequential`. Companion `description`. MessageTrace conductor panel (154).

## Tests code against

- Parent EXECUTE + worker DRAFT: worker ctx is DRAFT; a prior worker EXECUTE in the same loop already ran.
- AWAIT_CONFIRMATION: `run` mock call count 0 until approve.
- Two `request_id`s: clear one, the other `get_pending` still returns.
- Parallel compound tests unchanged.
- `import ze_core` absent from `ze_agents/delegate.py`.
