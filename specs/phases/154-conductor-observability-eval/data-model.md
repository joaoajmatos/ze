# Data model: Conductor observability

## MessageTrace (additive)

| Field | Type | Meaning |
|---|---|---|
| `conductor_hint` | list or null | Haiku subtasks (agent + prompt snippet) |
| `conductor_ledger` | list | `{agent, status, request_id?}` |
| confirmation ids | derived from ledger `request_id` or explicit list | 113 ids |

Statuses match 153: `planned` | `running` | `done` | `awaiting_confirmation` | `denied` | `skipped` | `ask_user`

## Progress locale

```text
conductor.checking_calendar → user-visible checking calendar copy
conductor.drafting_mail → user-visible drafting mail copy
```

## Eval scenarios

| id | Primary claim |
|---|---|
| `conductor_sequential_calendar_email` | Companion; event id in second brief |
| `routing_independent_parallel_not_companion` | Not companion primary |
| `conductor_speech_act_146_honest` | Nested cancel; no dual forget |
| `conductor_mid_sequence_confirmation` | CONFIRM invocation (e.g. calendar create) pauses; after approve the next specialist continues |
