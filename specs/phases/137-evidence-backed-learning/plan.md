# Implementation Plan: Evidence-Backed Goal Learning

**Branch**: `137-evidence-backed-learning` | **Date**: 2026-09-15 | **Spec**: [spec.md](./spec.md)

## Summary

Hard-cut the current dual goal-learning stores into one evidence-bearing model. Goal outcomes arrive uniformly from Phase 136 as `ActionRecord`s; learning records reference those outcomes, carry shared claim doctrine, and progress through review, contradiction, retraction, and promotion states. The action record remains the raw verified outcome. A generalized lesson begins as `INFERENCE`, can be promoted only after evidence-diversity and consistency gates, and becomes `FACT` only with directly supporting evidence or explicit user confirmation. Planner/executor retrieval and priority receive only active eligible claims, with inference labels preserved.

## Technical Context

**Language/Version**: Python 3.12; TypeScript/React for goal-review UI  
**Primary Dependencies**: `ze_automation.goals`, Phase 136 ActionRecord contract, `ze_agents.claims`, `ze_memory` licensed contribution path, existing NLI contradiction utility  
**Storage**: New `ze-automation` tables owned by a `zc` migration; destructive removal of `goals.learnings` and `goal_learnings` in the same migration chain  
**Testing**: pytest with `AsyncMock` pools/LLMs; API route tests; web Vitest; no real database or OpenRouter calls  
**Target Platform**: Backend, `/api/v0/goals` detail/review API, goal web detail  
**Performance Goals**: Constant-query goal detail for paged learning summaries; evidence-diversity decisions use indexed links, not raw action payload scans  
**Constraints**: Phase 136 must be available; no compatibility readers/writers; no `signal_sources()` changes; no generic contribution arbitration  
**Scale/Scope**: Goal domain persistence, executor/planner, memory promotion, REST/client/web detail, seed/reset and tests

## Constitution Check

| Principle | Check | Result |
|---|---|---|
| I. Spec-First | Complete spec, research, data model, contract, quickstart, and tasks are present | PASS |
| II. Single-User | No tenancy additions | PASS |
| III. Layered Package Architecture | Core implementation belongs in `ze-automation`; API/web consume contracts; no plugin imports of engine internals | PASS |
| IV. Typed, Explicit Python | Dataclasses, enum-backed lifecycle, typed domain errors, explicit store protocol | PASS |
| V. Test Discipline | Migration, store, executor, planner, promotion, API, consumer, and web tests are planned | PASS |
| VI. Explicit Persistence | Migration owns all new/removed schema in `ze-automation` | PASS |
| VII. One LLM Gateway | Existing planner client only; no new provider | PASS |
| VIII. Pre-v1 Hard Cuts | One authoritative model; legacy table/blob are removed without shims, dual writes, or dual reads | PASS |

## Project Structure

### Documentation

```text
specs/phases/137-evidence-backed-learning/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── contracts/learning-promotion.md
├── quickstart.md
├── tasks.md
└── checklists/requirements.md
```

### Source Code

```text
core/automation/ze-automation/
├── ze_automation/goals/types.py
├── ze_automation/goals/store.py
├── ze_automation/goals/postgres.py
├── ze_automation/goals/planner.py
├── ze_automation/goals/executor.py
├── ze_automation/goals/learning.py             # eligibility, diversity, contradiction rules
├── ze_automation/migrations/versions/zc0xx_evidence_backed_learning.py
└── tests/goal_engine/
apps/ze-api/
├── ze_api/api/schemas.py
├── ze_api/api/routes/goals.py
└── tests/api/
packages/ze-client/                              # regenerated OpenAPI client
apps/ze-web/src/
├── entities/goal/
├── features/review-goal-learning/
└── widgets/goal-detail/
core/ops/ze-seed/ze_seed/domains/automation.py
core/ops/ze-onboarding/ze_onboarding/reset.py
```

**Structure Decision**: Put learning lifecycle/rules beside the goal aggregate in `ze-automation`. The model depends on Phase 136 via its public action-record contract, never by re-creating action storage. Memory receives promotion through its existing contribution interface; no new public ungated fact writer is introduced.

## Delivery Phases

1. Confirm Phase 136 contract and identify all legacy reads/writes.
2. Establish types, errors, migration, store protocol, and authoritative store tests.
3. Change executor/planner from append/blob operations to evidence-backed candidates and eligible retrieval.
4. Implement promotion, review, contradiction, retraction, and consumer filtering.
5. Replace goal API/client/UI detail, update seeds/resets, remove legacy schema/accesses, and run full verification.

## Complexity Tracking

| Risk | Mitigation |
|---|---|
| ActionRecord contract differs from assumptions | Block implementation until Phase 136 exposes stable id, verification state, context/lineage, and safe summary; do not introduce a local substitute |
| Legacy blob has ambiguous provenance | Migrate it as imported historical context only where representable; never count it as independent evidence |
| Broad inference promoted too aggressively | Enforce explicit claim kind, consistency, and independent-context gates in one tested service |
| Retraction leaves stale prompt context | Centralize `list_eligible_learnings` and make planner/executor/priority use it |
