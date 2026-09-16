# Implementation Plan: Parallel Per-Subtask Gates

**Branch**: `158-parallel-subtask-gates` | **Date**: 2026-09-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/phases/158-parallel-subtask-gates/spec.md`

## Summary

Independent parallel compound no longer uses strictest-wins. Each subtask gets its own `CapabilityGate` + budget decision. EXECUTE/DRAFT jobs run now; AWAIT jobs confirm by `request_id`; BLOCKED jobs skip. Conductor stays 152. 153/155 rewrite unchanged. Sequential fan-out execute stays deleted.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: `CapabilityGate`, `GateDecision`, `pending_confirmations` / 113 `request_id`, `_execute_compound`, `synthesize`

**Storage**: Graph state `subtask_gate_decisions` only; existing confirmation table

**Testing**: pytest `test_execution.py` (replace strictest-wins); confirmation resume for one of two subtasks; conductor tests must still pass

**Target Platform**: Conversation graph compound path only

**Project Type**: Orchestration hard-cut (S/M, oversized vs 5-file guardrail)

**Performance Goals**: Same gather cost for all-EXECUTE; no extra LLM for gating

**Constraints**: Principle VIII; do not import calendar/messenger into companion; `ze-agents` must not import `ze_core`

**Scale/Scope**: `capability_check` + `_execute_compound` + edges + tests + optional eval id

## Constitution Check

| Principle | Check | Result |
|---|---|---|
| I. Spec-First | Spec 158 | PASS |
| II. Single-User | No `user_id` | PASS |
| III. Layered Package Architecture | Engine graph only | PASS |
| IV. Typed, Explicit Python | Dataclass/list on state, not Pydantic in domain | PASS |
| V. Test Discipline | Fail-first replace strictest-wins test | PASS |
| VI. Explicit Persistence | No new tables; 113 confirmations | PASS |
| VII. One LLM Gateway | No new LLM | PASS |
| VIII. Pre-v1 Hard Cuts | Delete min() behavior; no shim dual path | PASS |

**Post-design re-check**: Compound AWAIT must not use `draft_response` on `subtasks[0]` as a proxy for the whole envelope. PASS if edges send mixed compound to `execute_tool`.

## Project Structure

```text
specs/phases/158-parallel-subtask-gates/

core/engine/ze-core/ze_core/orchestration/nodes/execution.py
core/engine/ze-core/ze_core/orchestration/edges.py
core/engine/ze-core/ze_core/orchestration/state.py
core/engine/ze-core/tests/orchestration/nodes/test_execution.py
eval/scenarios/   # optional parallel mixed-decision id
```

**Structure Decision:** Partition inside `_execute_compound` after per-subtask `capability_check`. Single-agent path untouched.

## Complexity Tracking

> Guardrail: >5 files / ~12 tasks — full pipeline, not simple fold.
