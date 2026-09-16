# Implementation Plan: Action Instrumentation

**Branch**: `136-action-instrumentation` | **Date**: 2026-09-15 | **Spec**: [spec.md](./spec.md)

## Summary

Instrument existing action producers after their domain outcome is durable. Each producer derives a stable observation identity from its authoritative source record, submits one Phase 135 `ActionRecord` through the contribution seam, and carries applicable turn, automation, and channel context. A genuine pending observation is followed by one causally linked immutable terminal observation, per Phase 135. Producers retain all domain lifecycle, recovery, and retry authority.

## Technical Context

**Language/Version**: Python 3.12  
**Primary Dependencies**: Phase 135 ActionRecord ledger and contribution submit contract; existing workspace, messenger, calendar, automation, and prospecting stores  
**Storage**: Phase 135 action-record storage plus current producer-owned tables; this phase adds no competing operational-history table  
**Testing**: pytest with `AsyncMock`; package-specific unit tests plus ledger integration-contract tests; no real provider/DB/LLM calls  
**Target Platform**: Backend composition only  
**Project Type**: Cross-package producer instrumentation  
**Performance Goals**: Instrumentation is bounded, retry-safe, and does not add a blocking provider call after the producer outcome  
**Constraints**: Record after outcome known; one action record per stable producer identity; domain store remains source of truth; no compatibility shim or dual operational history  
**Scale/Scope**: Seven producer families: workspace, messenger, calendar, reminders, goals, workflows, prospecting

## Constitution Check

| Principle | Check | Result |
|---|---|---|
| I. Spec-First | Spec includes user stories, state semantics, contracts, and tasks | PASS |
| II. Single-User | Context IDs are correlation fields, not tenancy | PASS |
| III. Layered Package Architecture | Each domain emits through the Phase 135 contract; it does not import another plugin’s store | PASS |
| IV. Typed, Explicit Python | Outcome and source references are typed contract values | PASS |
| V. Test Discipline | Per-producer idempotency, chronology, and mapping tests are required | PASS |
| VI. Explicit Persistence | Phase 135 owns the ledger; producer tables remain owned by their domains | PASS |
| VII. One LLM Gateway | No LLM work | PASS |
| VIII. Pre-v1 Hard Cuts | Replace obsolete producer callbacks/contracts directly; no shim or dual history | PASS |

## Project Structure

### Documentation

```text
specs/phases/136-action-instrumentation/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── contracts/action-instrumentation.md
├── quickstart.md
├── tasks.md
└── checklists/requirements.md
```

### Anticipated Source Areas

```text
core/ops/ze-workspace/                 # workspace run terminalization
plugins/ze-messenger/                  # outbound send result
plugins/ze-calendar/                   # calendar and reminder mutations
core/automation/ze-automation/         # goal/workflow execution traces
plugins/ze-prospecting/                # outreach attempts
apps/ze-api/ze_api/container.py        # inject Phase 135 recorder where required
# Phase 135 action ledger package owns record type/store/migration
```

**Structure Decision**: Producers call a narrow injected `ActionRecorder`/Phase 135 ledger contract after committing their source-of-truth outcome. Shared mapping helpers belong with the ledger only when two or more producers share semantics; a domain-specific mapping remains local.

## Implementation Sequence

1. Confirm the Phase 135 contract supports source references, idempotent upsert, context IDs, and pending transition.
2. Add composition/injection at producer boundaries without creating cross-plugin imports.
3. Instrument terminal workspace and messenger paths first, then calendar/reminders, then automation and outreach.
4. Add failure/replay/pending coverage beside each producer.
5. Run targeted package tests and a repository scan proving excluded perception/arbitration paths were untouched.

## Complexity Tracking

No constitutional violation. This is intentionally broad in call sites but narrow in behavior: an audit projection of actions already performed.
