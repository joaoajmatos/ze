# Contract: Fat `delegate_to_agent` ACI

Identifiers from the spec’s Verbatim Constraints: `delegate_to_agent`, `agent_name`, `objective`, `prior_outputs`, `inputs`, `output_shape`, `stop_condition`, `tool_calls`, `response`, `plan_sequential`, `dynamic_plan_steps`, companion `description`, max depth **1**, inherited `gate_decision`, Principle VIII.

## Tool schema

```text
name: delegate_to_agent
required: agent_name, objective
optional: prior_outputs, inputs, output_shape, stop_condition
forbidden: task, context
```

Listed on: companion only.

## `run_delegate` outcomes

| Condition | Effect |
|---|---|
| Caller name ≠ `companion` | Failed `ToolCall`; specialist not started |
| `agent_name` is `companion` or empty | Failed `ToolCall` |
| Parent `_delegate_depth` ≥ 1 | Failed `ToolCall` (max depth 1) |
| Empty `objective` | Failed `ToolCall` |
| Unknown `agent_name` | Failed `ToolCall` (existing) |
| Otherwise | Isolated `run`; `result = {response, tool_calls}` |

`agentic_loop` MUST pass `self.name` as caller. Do not use `ctx.intent` as caller.

## Prompt assembly (normative labels)

Worker user content includes, when present:

- Objective: `<objective>`
- Prior outputs: `<prior_outputs>`
- Inputs: `<inputs>`
- Output shape: `<output_shape>`
- Stop: `<stop_condition>`

## 146 speech-act (still valid)

| User means | Companion calls |
|---|---|
| Timed remind / cancel reminder | `agent_name=reminders`, `objective=...` |
| Close/drop loop | `agent_name=loops`, `objective=...` |
| Abandon goal | `agent_name=goals`, `objective=...` |

Nested `cancel_reminder` / `close_loop` / `drop_loop` / `abandon_goal` still earn 146 confirmations.

Phase 152 MAY add optional `intent` without restoring `task`/`context`.

## Explicit non-contract (this phase)

- Conversation graph nodes/edges, including `plan_sequential` → END
- Companion class `description` (embedding text)
- Per-delegate `CapabilityGate` (152)
- Sequential routing to companion (153)

## Tests code against

- Schema required fields are `agent_name`, `objective`; properties omit `task` and `context`.
- Parent `companion` + fat fields → worker prompt contains each provided section; result has `tool_calls`.
- Parent `research` (or any non-companion) → failure, `run` not called.
- Depth 1 parent → failure.
- Target `companion` → failure.
- Research `tools` does not include `delegate_to_agent`.
- Companion `description` equals pre-phase string in a lock test or explicit snapshot.
- Graph `after_decompose` sequential still returns `plan_sequential`.
