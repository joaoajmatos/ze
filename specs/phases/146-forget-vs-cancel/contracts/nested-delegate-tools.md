# Contract: Nested delegate tool_calls

Identifiers from the spec: `cancel_reminder`, `abandon_goal`, `close_loop`, `ok`, Principle VIII.

## `delegate_to_agent` result

`run_delegate` MUST set `ToolCall.result` to a mapping:

```text
{"response": <specialist AgentResult.response>, "tool_calls": <specialist AgentResult.tool_calls>}
```

- MUST NOT return a bare response string (deleted dual door).
- Nested list MUST include the specialist’s tool calls for this sub-run (empty list if none).
- `ToolCall.success` on the delegate call remains exception-based; it MUST NOT be treated as domain-cancel success.

## Honesty consumers

Companion (and any agent that confirms domain cancel after a handoff) MUST inspect nested payloads:

| Nested `tool_name` | Earned iff |
|---|---|
| `cancel_reminder` | Result mapping has `cancelled` and no `error` |
| `abandon_goal` | Result mapping has `status` `abandoned` |
| `close_loop` | Result mapping indicates closed state and no `error` |
| `drop_loop` | Result mapping indicates dropped state and no `error` |
| `forget_fact` | Payload `ok` is true (unchanged) |

## Tests code against

- Delegate result is a mapping with `response` and `tool_calls`.
- Nested `cancel_reminder` `{error: ...}` does not earn a cancelled confirmation.
- Nested success earns domain confirmation, not a forgotten-fact confirmation.
