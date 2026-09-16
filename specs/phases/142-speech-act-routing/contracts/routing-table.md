# Contract: Routing table R1–R14

Normative copy lives in `spec.md`. Implementers MUST NOT dual-write the same clause to fact and reminder.

## Conflict rule

1. Time trigger → `reminder` (not `fact`) — R3, R4, R8, R11
2. Multi-week outcome → `goal` (not `loop`) — R6 beats R5
3. Explicit standing preference → `remember_fact` / `fact` — R1
4. No matching row → `clarify` or `loop`, never silent fact — R13

## Tool mapping (companion)

| SpeechAct | Tool / handoff |
|---|---|
| `fact` | `remember_fact` (explicit) or empty (extraction only) |
| `forget` | `forget_fact` |
| `reminder` | `delegate_to_agent` → reminders |
| `loop` | existing loop inflow / loop tools if any; else delegate |
| `goal` | `delegate_to_agent` → goal agent |
| `ingest` | existing ingest path (not `remember_fact`) |
| `drop` | none |
| `clarify` | one question; no write |

## Deferred

Constraint veto on mail/calendar (roadmap P5).
