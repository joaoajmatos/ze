# Contract: Conductor stall / replan

Identifiers: `stalled`, `replanned`, `ask_user`, `prior_outputs`, `inputs`, `delegate_to_agent`, `conductor_ledger`, `MessageTrace`, Principle VIII.

## Caps (normative)

- Per specialist name per turn: **2** successful-or-attempted `delegate_to_agent` calls.
- Per conductor turn: **6** attempted `delegate_to_agent` calls.
- Silent retries after stall: **1** per specialist name.

## Policy

| Event | Engine |
|---|---|
| First stall | Ledger `stalled`; next call to **same** name allowed if caps remain; that next call must carry stall context in `prior_outputs` or `inputs`; ledger `replanned` when issued |
| Second stall or cap | Block specialist `run`; tool result instructs ask; ledger `ask_user` |
| `awaiting_confirmation` | Not stall |

## Tests code against

- First stall → second invoke same agent with non-empty `prior_outputs`.
- Third invoke same agent → no specialist `run`.
- Seventh invoke any agents → blocked by turn cap.
- Confirmation path not counted as stall.
- Parallel compound tests unchanged (no stall wrapper).
- No `GoalStore.create` / workflow insert in stall tests.
- Eval or unit id `conductor_stall_then_ask` (or equivalent) exists.

## Companion instructions

MUST mention one silent retry then ask; MUST NOT claim unlimited replanning.
