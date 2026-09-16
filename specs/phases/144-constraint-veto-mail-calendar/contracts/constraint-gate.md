# Contract: `constraint_gate`

Identifiers from the spec: `constraint_gate`, `constraint`, Principle VIII, `ze_sdk`, `ze_core`.

## Decorator

`@tool(..., constraint_gate: bool = False, constraint_describe: Callable | None = None)`

- Default `constraint_gate` false.
- Stored on `ToolSpec`. No public alias that runs the old ungated write.

## Dispatch

Before a `constraint_gate` tool executes, the harness hook:

1. Builds `ConstraintWriteView` (describe or default).
2. Loads reviewed, current `constraint` facts.
3. Allows, confirms, or refuses per matching rules.
4. Must not call the tool function on refuse/confirm-hold.

## Tests code against

- Unmarked `remember_fact` is not intercepted.
- Marked test-double tool (not `send_email`) is intercepted — proves no name list in core.
- `send_email` / calendar mutations / `set_reminder` are marked.
