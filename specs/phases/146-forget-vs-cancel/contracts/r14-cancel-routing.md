# Contract: R14 cancel routing

Identifiers from the spec’s Verbatim Constraints: `forget_fact`, `cancel_reminder`, `abandon_goal`, `close_loop`, R14, Principle VIII, `ze_sdk`, `ze_core`.

## Primary store (one speech act)

| User means | Companion does | Must not |
|---|---|---|
| Cancel/forget a reminder | `delegate_to_agent` `agent_name=reminders`; specialist runs `cancel_reminder` | `forget_fact` for that utterance |
| Close/drop/forget a lingering concern | `delegate_to_agent` `agent_name=loops`; specialist runs `close_loop` or `drop_loop` | `forget_fact` for that utterance |
| Abandon/forget a goal | `delegate_to_agent` `agent_name=goals`; specialist runs `abandon_goal` | `forget_fact` for that utterance |
| Forget a named biography fact (R2) | `forget_fact` | Domain cancel of an unmatched reminder/loop/goal that only shares a word |

Plugin code MUST import `ze_sdk` (or the owning package). MUST NOT import `ze_core`.

## Extractor

- Cancel/drop/abandon aimed at reminder/loop/goal → `speech_act` `reminder` / `loop` / `goal`.
- Biography retract → `forget`.
- `facts` empty unless `speech_act` is `fact`.
- Reminder vs loop: time trigger still wins (Phase 142). Do not emit two primary acts for one clause.

## Dual-write (forbidden)

A single cancel speech act MUST NOT both succeed a domain cancel tool **and** return `forget_fact` `ok` true unless the user **named** both a biography fact and a domain item.

Domain failure MUST NOT fall back to `forget_fact`.

## Tests code against

- Seed dentist reminder + unrelated dentist-word fact; “forget the dentist” as cancel → reminder cancelled; fact live; no `forget_fact` `ok` true.
- “Forget that I like aisle seats” + dentist reminder → fact retracted; reminder remains.
- Loop and goal analogues with `close_loop` / `abandon_goal`.
