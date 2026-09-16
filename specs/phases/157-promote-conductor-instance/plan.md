# Implementation Plan: Promote Conductor Instance to Workflow/Goal

**Branch**: `157-promote-conductor-instance` | **Date**: 2026-09-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/phases/157-promote-conductor-instance/spec.md`

## Summary

When a conductor job must outlive the turn, companion offers (or, after explicit keep-going / offer accept, creates) a **goal** or **workflow** instance via 151 `delegate_to_agent` to `goals` / `workflow`. Timeout and abort offer, never silent insert. Procedures and in-chat conductor replacement are forbidden. 155/156 must already be Implemented.

## Technical Context

**Language/Version**: Python 3.12; optional ze-web copy if offer uses existing confirm primitives

**Primary Dependencies**: `delegate_to_agent`, GoalAgent `create_goal`, WorkflowAgent `create_workflow`, `confirmation_timeout`, notifications, `conductor_ledger`

**Storage**: Existing goals/workflows tables only; additive trace flag for offer; no procedure tables

**Testing**: pytest timeout/offer; companion prompt tests; no procedure store mocks called

**Target Platform**: Conductor close paths + confirmation timeout

**Project Type**: Durable escape hatch (L)

**Performance Goals**: No extra LLM required to decide “unfinished ledger” (deterministic)

**Constraints**: Plugin isolation; 152 CONFIRM on create; Principle VIII no procedure shim

**Scale/Scope**: Companion instructions + timeout/abort offer helper + tests + eval id; optional notification copy

## Constitution Check

| Principle | Check | Result |
|---|---|---|
| I. Spec-First | Spec 157 | PASS |
| II. Single-User | No `user_id` | PASS |
| III. Layered Package Architecture | Create via plugin/core automation agents; companion only delegates | PASS |
| IV. Typed, Explicit Python | Offer helper on ledger, not Pydantic in domain | PASS |
| V. Test Discipline | Fail-first offer vs insert | PASS |
| VI. Explicit Persistence | Existing goal/workflow migrations only | PASS |
| VII. One LLM Gateway | Type disambiguation may use companion’s existing turn LLM, not a new gateway | PASS |
| VIII. Pre-v1 Hard Cuts | No procedure dual-write; no wrap of conductor as workflow engine | PASS |

**Post-design re-check**: Timeout path today only says “try again” — extend that copy/offer, do not add a second timeout waiter. PASS.

## Project Structure

```text
specs/phases/157-promote-conductor-instance/

plugins/ze-personal/ze_personal/agents/companion/agent.py
apps/ze-api/ze_api/api/websocket/confirmation.py   # timeout offer when conductor unfinished
core/engine/ze-core/  # optional should_offer_promote(ledger) helper
eval/scenarios/conductor.yaml
```

**Structure Decision:** Deterministic “unfinished conductor” helper in engine (ledger statuses); user language and goal-vs-workflow choice in companion; create only via nested `goals`/`workflow` tools.

## Complexity Tracking

> None
