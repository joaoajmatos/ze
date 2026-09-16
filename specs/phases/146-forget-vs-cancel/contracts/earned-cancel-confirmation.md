# Contract: Earned cancel confirmation

Identifiers from the spec: `forget_fact`, `ok`, `cancel_reminder`, `abandon_goal`, `close_loop`, Principle VIII.

## Forgotten-fact claims (Phase 143, unchanged)

`earned_forget` iff some call named `forget_fact` (this turn, including nested delegate `tool_calls`) has payload `ok` true.

If not `earned_forget`, user-visible text MUST NOT claim a biography fact is forgotten (`I forgot`, `I've forgotten`, `forgotten that`, `wiped`, `já esqueci` if implemented).

Domain cancel success MUST NOT set `earned_forget`.

## Domain-cancel claims (this phase)

| Claim class | Earned iff |
|---|---|
| Reminder cancelled | `cancel_reminder` success payload this turn (local or nested) |
| Loop closed or dropped | `close_loop` or `drop_loop` success payload this turn |
| Goal abandoned | `abandon_goal` success payload this turn |

If not earned, strip claiming sentences (cancelled the reminder / closed the loop / abandoned the goal, close English equivalents). If nothing usable remains, use honest miss copy (e.g. `I could not cancel that.` / `I could not close that.` / `I could not abandon that.`). Acknowledgements without a success claim (`okay`) stay.

Mixed sentence that confirms an earned domain cancel and invents a forgotten fact: drop that sentence (fail closed).

## Turn path

- `CompanionAgent.run` already gates via `enforce_memory_confirmations`; extend that pass (same module) so domain claims are checked after nested `tool_calls` are visible.
- `RemindersAgent` / `GoalAgent` / `loops` MUST NOT confirm their write if the tool payload is a failure — apply the same domain-claim strip on their `AgentResult.response` (direct routing, not only companion).
- Prompt-only instructions do not satisfy this contract.

## Tests code against

- Successful `cancel_reminder`, no `forget_fact` `ok` → may say the reminder was cancelled; MUST NOT say a fact was forgotten.
- `forget_fact` `ok` false on cancel-shaped speech → no forgotten-fact confirmation.
- Unearned “I’ve cancelled your reminder” with no successful `cancel_reminder` → stripped / fallback.
