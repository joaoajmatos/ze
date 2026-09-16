# Data model: Earned confirmations and forget match

No new Postgres tables. This phase reshapes in-memory turn objects and the forget match result.

## Tool outcome (existing payload, now normative for the gate)

| Field | remember_fact | forget_fact |
|---|---|---|
| `ok` | bool | bool |
| `id` | uuid string when `ok` | — |
| `ids` | — | uuid strings when `ok` |
| `error` | string when not `ok` | string when not `ok` (`no matching fact` on miss) |

`ToolCall.success` is not a substitute for `ok`.

## Confirmation gate (new, companion-local)

| Field | Meaning |
|---|---|
| `response` | Model text before the gate |
| `tool_calls` | This turn’s `ToolCall` list |
| `earned_remember` | Any `remember_fact` payload with `ok` true |
| `earned_forget` | Any `forget_fact` payload with `ok` true |
| `gated_response` | Text after strip/replace |

State is per turn, not persisted.

## Forget match (existing rows, new selection rules)

Input: `query: str`. Scan live (`contradicted = false`) facts, cap 200 rows as today.

Match classes (first class that yields rows wins; later classes do not add more):

1. **Exact identity** — normalized predicate or value equals normalized query. All exact hits retract (duplicate rows of the same identity).
2. **Named value** — full stored value is a contiguous phrase in the query (value min length 8 or 2+ tokens).
3. **Long query phrase in value** — query has ≥ 3 tokens and appears as a contiguous phrase in value.
4. **Unique embedding** — at most one row, cosine ≥ 0.88, runner-up < 0.80.

If a class yields zero rows, try the next. If a class yields rows, stop. Empty query → no rows, no `UPDATE`.

Output: list of fact ids passed to the existing `UPDATE ... contradicted = true`. Empty list → `forget_fact` `ok` false.

## Transitions

```text
model reply
  → parse tool ok
  → earned? keep confirmation
  → else strip claiming sentences / fallback copy
  → flush gated text to user
```

```text
forget query
  → exact → named value → long phrase → unique embedding → miss
  → miss never writes
```
