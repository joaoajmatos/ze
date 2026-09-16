# Data model: Mixed gather+act conductor

No new persisted entities. Classification is a pure function of decompose `SubTask` list.

## Intent families (closed this phase)

| Family | Intent strings (case-insensitive) |
|---|---|
| Gather | `read`, `lookup`, `search` |
| Act | `create`, `update`, `delete`, `send` |
| Unclassified | everything else (`manage`, `reason`, empty, unknown) |

## Rewrite predicates

| Condition | Result |
|---|---|
| `is_sequential` and `len(subtasks) > 1` | Rewrite (153) |
| Distinct agents > 1 and ≥1 gather and ≥1 act | Rewrite (155), even if `is_sequential` is false |
| All gather, sequential false, compound | No rewrite; fan-out + synthesize |
| Distinct agents ≤ 1 and not (sequential and len>1) | Specialist primary |
| All act, sequential false | No rewrite (parallel path; strictest-wins) |

## Envelope after rewrite (unchanged from 153)

Companion primary, original user prompt, `is_compound=False`, `conductor_hint` = former subtasks, `is_sequential` MAY be set true on the rewritten envelope so downstream “conductor turn” checks stay simple (research: set `is_sequential=True` on rewrite as 153 already does).
