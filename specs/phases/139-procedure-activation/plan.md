# Implementation Plan: Governed Procedure Activation

**Branch**: `139-procedure-activation` | **Date**: 2026-09-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/phases/139-procedure-activation/spec.md`

## Summary

Phase 139 consumes Phase 138's governed procedure versions and makes only validated, enabled versions discoverable to relevant agents and planners. A shared matcher evaluates trigger and preconditions, an explicit invocation records the selected immutable version, and each guided action remains capability-gated with tools narrowed by intersection. Invocation outcomes feed Phase 138's review/confidence path. A small procedure management surface exposes list, detail/evidence/outcomes, governed edit, and disable operations.

## Technical Context

**Language/Version**: Python 3.12; TypeScript/React for the management surface.

**Primary Dependencies**: Phase 138 `ze_memory.procedures` ProcedureIdentity/Candidate/Admission/Version/Feedback contracts and active-version retrieval; `ze_agents` agent/tool contracts; `ze_core` orchestration trace and capability gate; `ze_automation` goal/workflow planners; `ze_sdk`; `@ze/client`; React Query and Feature-Sliced Design UI.

**Storage**: Phase 138 owns procedure identity/version/admission/evidence/feedback persistence in `ze-memory`. This phase adds invocation/outcome persistence there only when its append-only `ProcedureFeedback` records cannot represent the action-level activation ledger; raw-SQL migration stays on the `zm` chain.

**Testing**: pytest with mocked asyncpg/LLM; API contract tests; Vitest for UI; `make test-memory`, `make test-core`, `make test-automation`, applicable plugin tests, `make test`, `make test-web`, `make lint`.

**Target Platform**: Backend API and React web client.

**Project Type**: Cross-package advisory procedure discovery and traceability feature.

**Performance Goals**: Procedure discovery is bounded to eligible candidates and completes within the existing planning/agent context-fetch budget; it must not add a second LLM call merely to determine eligibility.

**Constraints**: Advisory only; explicit invocation; existing capability checks remain authoritative; allowed tools can only be narrowed; no unreviewed execution; no signal source rewiring; no contribution arbitration. Pre-v1 hard cuts replace existing direct planner procedure retrieval.

**Scale/Scope**: Common discovery and invocation contracts, integrations for all context-bearing registered agents/planners, trace/outcome feedback, one minimal API/UI surface.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Spec-First | Spec 139 defines stories, requirements, boundaries, and tests | PASS |
| II. Single-User | No tenant, role, or user-id model | PASS |
| III. Layered Package Architecture | Procedure lifecycle/discovery stays in its owning cognition package; agents/plugins consume public SDK contracts; API composes; web follows FSD | PASS |
| IV. Typed, Explicit Python | Dataclasses/protocols and typed errors; no inline imports or bare domain exceptions | PASS |
| V. Test Discipline | Unit, integration, contract, and web tests are planned without live DB/LLM | PASS |
| VI. Explicit Persistence | Activation records, if absent from Phase 138, use an owner-package raw-SQL migration | PASS |
| VII. One LLM Gateway | Trigger/precondition evaluation is deterministic against available context; no new provider or key | PASS |
| VIII. Pre-v1 Hard Cuts | Existing direct procedure retrieval is replaced, not retained as a compatibility path | PASS |

*Post-design re-check:* The precise owning package and migration revision depend on Phase 138's delivered lifecycle contract. No cross-layer dependency or dual interface is introduced; PASS remains conditional on adopting its public contract rather than reaching into implementation storage.

## Project Structure

### Documentation (this feature)

```text
specs/phases/139-procedure-activation/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── contracts/procedure-activation.md
├── quickstart.md
├── tasks.md
└── checklists/requirements.md
```

### Source Code (repository root)

```text
core/cognition/ze-memory/ze_memory/
├── procedures/                 # Phase-138 lifecycle; discovery/activation contracts
├── types.py                    # public Procedure value types if retained here
└── migrations/versions/        # only if activation ledger is not Phase-138-owned
packages/ze-sdk/ze_sdk/
└── memory.py or procedures.py  # public plugin-facing re-exports
core/engine/ze-core/ze_core/
├── orchestration/              # context injection, invocation trace/capability integration
└── telemetry or trace/         # trace schema/serialization as appropriate
core/automation/ze-automation/ze_automation/
├── goals/planner.py
└── workflow/                   # planner integration
plugins/*/                      # relevant context-bearing agent integrations only
apps/ze-api/ze_api/api/
├── routes/                     # procedure management REST routes
└── schemas.py                  # request/response models
apps/ze-web/src/
├── entities/procedure/         # query hooks, types, format helpers
├── features/procedure-review/  # edit/disable mutations
└── widgets/procedure-management/
```

**Structure Decision**: `ze-memory` owns Phase 138's lifecycle and therefore supplies the lifecycle-aware discovery, match, invocation, and feedback boundary. Agents/planners receive it through `ze_sdk`, and the API app is the composition root. The engine only attaches guidance to a turn and records capability-gated action trace data; it does not own procedure policy.

## T002 integration audit

Context-bearing production callers: LangGraph `fetch_context` (every routed agent), `GoalPlanner.plan` / `replan_remaining`, `WorkflowPlanner.plan`. Execution uses `invoke_procedure` plus `ProcedureActivator` from the composition root. Plugins do not retrieve procedures directly.


## Complexity Tracking

None.
