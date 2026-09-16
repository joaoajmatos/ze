# Data model: Fat Delegate ACI

No new Postgres tables.

## Fat brief (tool arguments)

| Field | Required | Type | Meaning |
|---|---|---|---|
| `agent_name` | yes | str | Registry name of the worker (not companion) |
| `objective` | yes | str | What the worker must achieve; replaces `task` |
| `prior_outputs` | no | str | Prior specialist text or ids for a later step |
| `inputs` | no | str | Extra facts (constraints, ids); replaces `context` |
| `output_shape` | no | str | Hint for the worker’s answer shape |
| `stop_condition` | no | str | Hint for when the worker should stop |

Validation: empty `objective` → failed `ToolCall`, no `run`. Unknown `agent_name` → failed `ToolCall` as today. Presence of `task` or `context` is not a supported ACI (schema omits them).

## Isolated worker context

| Field | Rule this phase |
|---|---|
| `prompt` | Assembled fat brief |
| `messages` | One user turn from that prompt |
| `intent` | Worker `agent_name` (unchanged from today) |
| `gate_decision` | Copied from parent (152 will replace) |
| `extensions["_delegate_depth"]` | Parent depth + 1; refuse if parent depth ≥ 1 |
| session `messages` | Unchanged; worker transcript stays local to the worker `run` |

## Delegate result (146, unchanged shape)

| Field | Type | Meaning |
|---|---|---|
| `response` | str | Specialist user-visible text |
| `tool_calls` | list | Nested tool records from `AgentResult.tool_calls` |

`ToolCall.success` on `delegate_to_agent` is still not a substitute for nested domain payloads.

## Caller allow-list (in-memory)

Legal parent: agent name `companion`. Legal target: any registered agent except `companion`. Depth: 0 → 1 only.

## Deleted

- `task`
- `context`
- `_DELEGATE_MAX_DEPTH == 2`
- Research listing `delegate_to_agent`
