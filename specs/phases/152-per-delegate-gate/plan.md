# Implementation Plan: Per-Delegate Capability and Confirmation

**Branch**: `152-per-delegate-gate` | **Date**: 2026-09-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/phases/152-per-delegate-gate/spec.md`

## Summary

Stop copying the parent `gate_decision` onto nested workers. At each `run_delegate`, evaluate `CapabilityGate` for specialist + declared or default intent, composed with spend budget. EXECUTE and DRAFT run that worker now; AWAIT_CONFIRMATION pauses the conductor via existing `request_id` confirmations and resumes that invocation. A lookup is never held for a later send. Graph parallel compound stays strictest-wins.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: `ze_agents.delegate.run_delegate`, `ze_core.capability.CapabilityGate`, `SpendBudgetChecker`, confirmation store (113), `tool_interrupt_fn`

**Storage**: Existing `pending_confirmations` (`request_id` PK). No new migration.

**Testing**: pytest on `test_delegate.py` plus confirmation isolation tests; mock gate and budget; no real DB required if confirmation store is mocked

**Target Platform**: Nested-tool path inside companion `agentic_loop`

**Project Type**: Hard-cut of inherited nested gates

**Performance Goals**: One `evaluate` per delegate; no extra LLM

**Constraints**: `ze-agents` must not import `ze_core` — inject a protocol. Do not retune specialist Mode tables. Do not start 153/154.

**Scale/Scope**: Delegate + execute_tool wiring + confirmation interrupt kind for delegate invocations

## Constitution Check

| Principle | Check | Result |
|---|---|---|
| I. Spec-First | Spec 152; depends on 151 Implemented at product time | PASS |
| II. Single-User | No `user_id` | PASS |
| III. Layered Package Architecture | Gate implementation stays in ze-core; protocol in ze-agents; companion does not import specialist tools | PASS |
| IV. Typed, Explicit Python | Protocol + existing `GateDecision` | PASS |
| V. Test Discipline | Fail-first lookup-vs-write and request_id isolation | PASS |
| VI. Explicit Persistence | Reuse zc027 `request_id` PK; no new table | PASS |
| VII. One LLM Gateway | No new LLM | PASS |
| VIII. Pre-v1 Hard Cuts | Delete wholesale inherit; no “inherit unless…” shim | PASS |

**Post-design re-check**: Dual gate (parent copy AND evaluate, then ignore evaluate) rejected. PASS.

## Project Structure

```text
specs/phases/152-per-delegate-gate/

core/contracts/ze-agents/ze_agents/delegate.py     # evaluate before run; optional intent; no parent copy
core/contracts/ze-agents/ze_agents/types.py        # optional protocol / context hook for gate
core/engine/ze-core/ze_core/orchestration/nodes/execution.py  # inject gate+budget into ctx
core/engine/ze-core/ze_core/conversation/confirmations/       # request_id persist (existing)
core/engine/ze-core/tests/orchestration/test_delegate.py
core/engine/ze-core/tests/orchestration/test_priority_confirmation_flow.py  # isolation lock
```

**Structure Decision:** Evaluation is a ze-core-wired callback; `run_delegate` stays in ze-agents. Confirmation uses 113, not a new bus.

## Complexity Tracking

> None
