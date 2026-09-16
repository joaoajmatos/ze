# Data model: Sequential routing hard-cut

## RoutingEnvelope (behavior)

| Flag | Meaning after this phase |
|---|---|
| `is_compound` and not `is_sequential` | Parallel independent; gather + synthesize |
| `is_sequential` and more than one subtask | Conductor: rewrite to companion primary; hint kept |
| one subtask | That specialist, even if `is_sequential` was true |

## Deleted state

- `dynamic_plan_steps`
- `dynamic_plan_high_risk`

## Added state (turn-local, not Postgres tables)

| Field | Meaning |
|---|---|
| `conductor_hint` | Optional list of Haiku subtasks (agent, prompt); never executed as a DAG |
| `conductor_ledger` | List of `{agent, status, request_id?}` this turn |

Statuses (closed): `planned` | `running` | `done` | `awaiting_confirmation` | `denied` | `skipped` | `ask_user`

## MessageTrace (additive)

Copy `conductor_hint` summary + `conductor_ledger` onto the trace object 154 will render. No new message table.

## Companion description

Embedding source string changes this phase (151 lock lifted).
