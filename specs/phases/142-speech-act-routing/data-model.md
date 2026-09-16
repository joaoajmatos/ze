# Data Model: Speech-Act Routing (Phase 142)

## SpeechAct (in-memory enum)

`fact` | `forget` | `reminder` | `loop` | `goal` | `ingest` | `drop` | `clarify`

Maps to spec rows:

| SpeechAct | Rows |
|---|---|
| `fact` | R1, R9 |
| `forget` | R2 |
| `reminder` | R3, R4, R8 (if time parses), R11 |
| `loop` | R5, R8 (if no time), R13 concern |
| `goal` | R6 |
| `ingest` | R7 |
| `drop` | R10, R12 (read-only; no write) |
| `clarify` | R13 no-row |

R14 is `forget` only when the target is a biography fact; otherwise the domain cancel tool (not a new enum value — companion hands off).

## Extraction output

```text
{ "speech_act": "<SpeechAct>", "facts": [ ... ] }
```

`facts` MUST be empty unless `speech_act == fact`.

No new persisted entity. Existing `Reminder`, `OpenLoop`, `Goal`, `Fact` types unchanged.
