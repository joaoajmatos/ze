# Contract: Sequential routing hard-cut

Identifiers: `plan_sequential` (deleted), `dynamic_plan_steps` (deleted), `dynamic_plan_high_risk` (deleted), `is_sequential`, `delegate_to_agent`, `MessageTrace`, companion `description`, Principle VIII.

## Graph

| Before | After |
|---|---|
| `after_decompose` → `plan_sequential` → END | `after_decompose` → `fetch_context` always (or rewrite then fetch_context) |
| `build_graph` adds `plan_sequential` node | Node absent |
| `_execute_compound(..., is_sequential=True)` loop | Function does not take a sequential execute path |

## Rewrite (normative)

```text
if envelope.is_sequential and len(envelope.subtasks) > 1:
    hint = envelope.subtasks
    envelope = companion primary, user prompt, not compound
    state.conductor_hint = hint
```

Haiku hint MUST NOT be dispatched as graph subtasks.

## Companion tools (unchanged list)

`remember_fact`, `forget_fact`, `delegate_to_agent` only. No calendar/messenger imports.

## Tests code against

- Former `test_after_decompose_sequential_goes_to_plan_sequential` **deleted**; new test: sequential multi → companion primary, next node fetch_context.
- Independent compound still `requires_synthesis` / gather.
- `plan_sequential` name absent from `graph.py` and `nodes/__init__.py`.
- `dynamic_plan_steps` absent from `AgentState` and `turn.py`.
- Companion `description` no longer says not for calendar/email.
- No workflow row inserted on a conductor unit test.
