# Implementation Plan: Response-Level Unsolicited Recitation

**Branch**: `145-unsolicited-recitation` | **Date**: 2026-09-16 | **Spec**: [spec.md](./spec.md)

## Summary

Phase 141 forbids unsolicited “I remember that you…” in the prompt. The model can still recite. Extend `enforce_memory_confirmations` so unsolicited biography recitation never reaches the user. Asked recall may state facts. Earned 143 confirmations stay. `TurnSurfacing` still owns open items. Do not implement 144.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: Companion `honesty.py`, `CompanionAgent.run` (already buffers sink)

**Storage**: None

**Testing**: Honesty unit tests + companion run tests; eval scenario; no real LLM

**Constraints**: Plugins never import `ze_core`. Principle VIII: one reply door.

## Constitution Check

| Principle | Check | Result |
|---|---|---|
| I. Spec-First | Spec 145 + this plan | PASS |
| II. Single-User | No `user_id` | PASS |
| III. Layered Package Architecture | Gate stays in `ze_personal` honesty; no `ze_core` import | PASS |
| IV. Typed, Explicit Python | Optional `user_text: str \| None` | PASS |
| V. Test Discipline | Fail-first honesty tests | PASS |
| VI. Explicit Persistence | No schema | PASS |
| VII. One LLM Gateway | Deterministic strip | PASS |
| VIII. Pre-v1 Hard Cuts | Extend the existing gate; no parallel recitation module | PASS |

**Post-design re-check**: Contract is the same function. PASS.

## Project Structure

```text
plugins/ze-personal/ze_personal/agents/companion/honesty.py
plugins/ze-personal/ze_personal/agents/companion/agent.py
plugins/ze-personal/tests/agents/companion/test_memory_claim_honesty.py
eval/scenarios/memory.yaml
```

## Complexity Tracking

> None
