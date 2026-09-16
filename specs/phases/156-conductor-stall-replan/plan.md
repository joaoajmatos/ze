# Implementation Plan: Conductor Stall / Replan

**Branch**: `156-conductor-stall-replan` | **Date**: 2026-09-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/phases/156-conductor-stall-replan/spec.md`

## Summary

Enforce a turn-local Magentic-One outer loop on companion `delegate_to_agent`: detect stall, allow one silent rebrief with new `prior_outputs`, cap flailing, write `stalled`/`replanned`/`ask_user` on `conductor_ledger`. Policy is in research.md and in the delegate path (ze-agents), not prompt-only. No durable automation rows. 155 must already route mixed gather+act here.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: `ze_agents.delegate.run_delegate`, `AgentContext.conductor_ledger`, companion instructions, `MessageTrace`

**Storage**: Turn/checkpoint state only (existing `conductor_ledger` + new counter fields on context/state)

**Testing**: pytest on delegate + ledger; optional eval YAML

**Target Platform**: Conductor nested-tool path

**Project Type**: Harness/delegate policy (M)

**Performance Goals**: No extra LLM for stall detection this phase

**Constraints**: Plugin isolation; 151/152/155 held; no workflow inserts

**Scale/Scope**: Delegate wrapper, state counters, companion prompt, tests, eval id

## Constitution Check

| Principle | Check | Result |
|---|---|---|
| I. Spec-First | Spec 156 | PASS |
| II. Single-User | No `user_id` | PASS |
| III. Layered Package Architecture | Enforce in `ze_agents.delegate` (companion-only tool already lives there); companion prompt in plugin | PASS |
| IV. Typed, Explicit Python | Dataclass counters on context or dict ledger entries | PASS |
| V. Test Discipline | Fail-first delegate tests | PASS |
| VI. Explicit Persistence | No new tables | PASS |
| VII. One LLM Gateway | Detector is deterministic this phase | PASS |
| VIII. Pre-v1 Hard Cuts | Additive ledger statuses; no shim dual judge | PASS |

**Post-design re-check**: Do not put stall policy only in YAML locales. PASS.

## Project Structure

```text
specs/phases/156-conductor-stall-replan/

core/contracts/ze-agents/ze_agents/delegate.py
core/contracts/ze-agents/ze_agents/types.py          # counters on AgentContext if needed
core/engine/ze-core/ze_core/orchestration/state.py   # if counters must checkpoint
plugins/ze-personal/ze_personal/agents/companion/agent.py
core/contracts/ze-agents/tests/ and/or ze-core tests/orchestration/test_delegate.py
eval/scenarios/conductor.yaml
```

**Structure Decision:** Policy constants + enforcement in `delegate.py`; ledger mutations there so the engine cannot be bypassed by prompt. Companion instructions mirror the policy.

## Complexity Tracking

> None
