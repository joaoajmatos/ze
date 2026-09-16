# Implementation Plan: Mixed Gather+Act → Conductor

**Branch**: `155-mixed-gather-act-conductor` | **Date**: 2026-09-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/phases/155-mixed-gather-act-conductor/spec.md`

## Summary

Extend `apply_conductor_rewrite` so mixed gather+act multi-specialist envelopes (intent families, not a two-agent list) take the same companion-primary path as 153 sequential multi-specialist turns, even when Haiku left `is_sequential` false. Independent all-read compound and single-domain specialists stay unchanged. Do not split parallel gates, stall, or promote.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: `RoutingEnvelope`, `SubTask`, `apply_conductor_rewrite` in `ze_core.orchestration.nodes.routing`

**Storage**: None (turn-local hint/ledger already exist)

**Testing**: pytest unit table on rewrite; optional eval YAML for sequential-false mixed pair

**Target Platform**: Conversation graph routing after decompose

**Project Type**: Routing predicate (S)

**Performance Goals**: No extra LLM; pure intent classification

**Constraints**: Do not restore `plan_sequential`. Do not change 152 parallel strictest-wins. Plugin companion still does not import messenger tools.

**Scale/Scope**: One predicate + tests + one eval scenario; 153/154 contracts held

## Constitution Check

| Principle | Check | Result |
|---|---|---|
| I. Spec-First | Spec 155 | PASS |
| II. Single-User | No `user_id` | PASS |
| III. Layered Package Architecture | Classification in engine routing (envelope already in ze-core); not a plugin agent-name list | PASS |
| IV. Typed, Explicit Python | Keep dataclasses; closed intent families as frozensets or helper | PASS |
| V. Test Discipline | Fail-first rewrite tests | PASS |
| VI. Explicit Persistence | No new tables | PASS |
| VII. One LLM Gateway | No new model | PASS |
| VIII. Pre-v1 Hard Cuts | Widen rewrite predicate in place; no dual sequential-only path left as a shim | PASS |

**Post-design re-check**: One `apply_conductor_rewrite`; no wrap of the old function. PASS.

## Project Structure

```text
specs/phases/155-mixed-gather-act-conductor/

core/engine/ze-core/ze_core/orchestration/nodes/routing.py
core/engine/ze-core/tests/orchestration/test_nodes.py
eval/scenarios/conductor.yaml   # additive mixed sequential-false id
```

**Structure Decision:** Same rewrite function as 153; add `is_mixed_gather_act` helper beside it. Do not classify inside plugins.

## Complexity Tracking

> None
