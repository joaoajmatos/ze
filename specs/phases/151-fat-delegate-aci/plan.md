# Implementation Plan: Fat Delegate ACI

**Branch**: `151-fat-delegate-aci` | **Date**: 2026-09-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/phases/151-fat-delegate-aci/spec.md`

## Summary

Upgrade `delegate_to_agent` so companion can brief an isolated specialist with a fat ACI (`objective`, optional `prior_outputs`, `inputs`, `output_shape`, `stop_condition`). Hard-cut `task` and `context`. Only companion may list or successfully call the tool; max depth is 1; research loses it and must not guess calendar. Nested `{response, tool_calls}` stays the 146 honesty surface. Do not touch the conversation graph, companion embedding `description`, `plan_sequential`, or parent `gate_decision` inheritance.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: `ze_agents.delegate.run_delegate`, `BaseAgent.agentic_loop`, companion and research `@agent` classes

**Storage**: None. No migrations.

**Testing**: pytest in `core/engine/ze-core/tests/orchestration/test_delegate.py` and companion/research agent tests; mock LLM and registry; no real OpenRouter

**Target Platform**: In-process agentic loop (not a new REST surface)

**Project Type**: Pre-v1 hard-cut of a harness tool ACI plus caller allow-list

**Performance Goals**: One specialist `run` per successful delegate; no extra LLM for brief assembly

**Constraints**: Principle VIII — no dual `task`/`objective` ACI. Principle III — companion must not import calendar/messenger tools. Do not start 152–154 product. `ctx.intent` is companion’s `reason`, not the agent name — caller identity must come from `BaseAgent.name`.

**Scale/Scope**: One harness module, two plugin agents, existing delegate tests, speech-act prompt strings that mention `task`

## Constitution Check

| Principle | Check | Result |
|---|---|---|
| I. Spec-First | Spec 151 + this plan; 152–154 specified separately, not implemented here | PASS |
| II. Single-User | No `user_id` | PASS |
| III. Layered Package Architecture | Delegate stays in `ze-agents`; plugins keep `ze_sdk` imports; companion does not gain calendar tools | PASS |
| IV. Typed, Explicit Python | Existing `ToolCall` mapping result; no new Pydantic in domain | PASS |
| V. Test Discipline | Fail-first tests for schema, caller allow-list, depth 1, speech-act `objective` | PASS |
| VI. Explicit Persistence | No tables | PASS |
| VII. One LLM Gateway | No new LLM path | PASS |
| VIII. Pre-v1 Hard Cuts | Delete `task`/`context`; same-phase caller and test updates; no alias | PASS |

**Post-design re-check**: Contract is the tool schema + `run_delegate` refuse rules + 146 result shape. Dual ACI rejected. PASS.

## Project Structure

```text
specs/phases/151-fat-delegate-aci/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── fat-delegate-aci.md
└── tasks.md

core/contracts/ze-agents/ze_agents/delegate.py            # schema, prompt assembly, caller+depth+target guards
core/contracts/ze-agents/ze_agents/base_agent.py          # pass self.name into run_delegate
core/engine/ze-core/tests/orchestration/test_delegate.py  # schema, fat brief, allow-list, depth 1
plugins/ze-personal/ze_personal/agents/research/agent.py  # drop tool; calendar limitation copy
plugins/ze-personal/ze_personal/agents/companion/agent.py # instructions: objective (+ optional fat fields); description UNCHANGED
plugins/ze-personal/tests/agents/companion/               # speech-act still uses delegate; 146 nested tool_calls
```

**Structure Decision:** The harness tool in `ze-agents` is the contract. Plugin agents only change tool lists and instruction strings. Graph files are out of this tree.

## Complexity Tracking

> None
