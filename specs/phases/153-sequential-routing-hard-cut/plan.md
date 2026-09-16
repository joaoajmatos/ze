# Implementation Plan: Sequential Routing Hard-Cut

**Branch**: `153-sequential-routing-hard-cut` | **Date**: 2026-09-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/phases/153-sequential-routing-hard-cut/spec.md`

## Summary

Route sequential/mixed/dependent multi-specialist turns to companion as primary. Delete `plan_sequential`, its END edge, `dynamic_plan_steps` / `dynamic_plan_high_risk`, and `_execute_compound`’s sequential loop. Independent parallel stays gather+synthesize; single-domain stays the specialist. Update companion `description` and conductor instructions. Record a turn-local ledger on `MessageTrace`. Do not promote to workflow/goal.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: `ze_core.orchestration.graph`, `edges.after_decompose`, `routing.fallback` / decompose, companion agent, `MessageTrace`

**Storage**: No new tables. Delete unused state fields (hard-cut).

**Testing**: pytest `test_edges.py`, `test_routing_nodes.py`, graph compile tests, companion description tests; no OpenRouter

**Target Platform**: Conversation graph + companion embeddings

**Project Type**: Pre-v1 routing hard-cut (L)

**Performance Goals**: No extra graph node vs today after delete; companion may use more LLM on mixed turns only

**Constraints**: Principle VIII — delete, do not wrap `plan_sequential`. Companion must not import plugin tools. Do not start 154 UI/eval files except ledger fields 153 owns.

**Scale/Scope**: Graph, routing types, companion agent strings, trace dataclass, many tests

## Constitution Check

| Principle | Check | Result |
|---|---|---|
| I. Spec-First | Spec 153; depends on 151–152 Implemented at code time | PASS |
| II. Single-User | No `user_id` | PASS |
| III. Layered Package Architecture | Routing in ze-core; companion still delegates; no calendar imports | PASS |
| IV. Typed, Explicit Python | Delete TypedDict fields; ledger dataclass | PASS |
| V. Test Discipline | Replace sequential→plan_sequential tests with companion primary | PASS |
| VI. Explicit Persistence | No new tables; unused columns only if any (expect in-memory state only) | PASS |
| VII. One LLM Gateway | Haiku decompose remains the hint | PASS |
| VIII. Pre-v1 Hard Cuts | Delete planner node this phase; no alias END wrapper | PASS |

**Post-design re-check**: Feeding prior outputs in `_execute_compound` sequential rejected (path deleted). PASS.

## Project Structure

```text
specs/phases/153-sequential-routing-hard-cut/

core/engine/ze-core/ze_core/orchestration/graph.py
core/engine/ze-core/ze_core/orchestration/edges.py
core/engine/ze-core/ze_core/orchestration/nodes/routing.py  # delete plan_sequential
core/engine/ze-core/ze_core/orchestration/nodes/execution.py  # delete sequential compound loop
core/engine/ze-core/ze_core/orchestration/state.py
core/engine/ze-core/ze_core/conversation/turn.py
core/engine/ze-core/ze_core/conversation/messages/types.py  # ledger on MessageTrace
core/engine/ze-core/ze_core/routing/fallback.py
plugins/ze-personal/ze_personal/agents/companion/agent.py
tests: edges, routing, graph, conversation turn, companion
```

**Structure Decision:** Rewrite envelope at decompose/`after_decompose` toward `fetch_context` with companion primary. Haiku steps stored as hint, never executed as a DAG.

## Complexity Tracking

> None. Size is oversized vs 5/10 guardrail; still one phase as the roadmap requires.
