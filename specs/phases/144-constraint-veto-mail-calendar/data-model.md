# Data model: Constraint veto on gated writes

No new Postgres tables.

## ToolSpec (existing, new fields)

| Field | Meaning |
|---|---|
| `constraint_gate` | Opt-in. Default false. |
| `constraint_describe` | Optional callable args → `ConstraintWriteView` |

## ConstraintWriteView (new, in-memory)

| Field | Meaning |
|---|---|
| `tool_name` | Registered tool |
| `kind` | Plugin string (`outbound_message`, `calendar_mutation`, `reminder_write`, …) |
| `channel` | Plugin string or none (`email`, `calendar`, `reminder`, …) |
| `parties` | Names/addresses for this write |
| `when` | Intended fire/send/start time, timezone-aware, or none |
| `summary` | Short natural-language act |

## Veto outcome (tool result mapping)

| Field | Meaning |
|---|---|
| `ok` | false when refused or held |
| `veto` | true iff the constraint hook ran and blocked or held |
| `constraint_ids` | ids of reviewed facts that applied |
| `error` | human-readable missive |

`ToolCall.success` is not a substitute for `veto` (function may return without throwing).

## Reviewed constraint (existing rows)

`memory_facts` where `reviewed = true`, `contradicted = false`, family/predicate `constraint`.

## Transitions

```text
call_tool(gated)
  → describe write
  → load reviewed constraints
  → allow | confirm | refuse
  → execute only on allow (or after user approve)
  → reply may claim veto only if veto true this turn
```
