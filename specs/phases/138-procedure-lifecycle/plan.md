# Implementation Plan: Governed Procedure Lifecycle

**Branch**: `138-procedure-lifecycle` | **Date**: 2026-09-15 | **Spec**: [spec.md](./spec.md)

## Summary

Hard-cut the scattered procedure writers into a single ProcedureAdmission service. A
`ProcedureCandidate`, carrying Phase 137 `Evidence` and `Learning` references plus honest
provenance, is the only input that can create an active versioned Procedure. The service
records review decisions, serializes supersession/rollback, and accepts append-only feedback
linked to existing action records. Existing goal-local provisional procedures obtain an explicit
completion, discard, or recovery outcome. `MemoryStore.propose_procedure` and the dream
promoter's direct INSERT are removed without compatibility aliases.

## Technical Context

**Language/Version**: Python 3.12  
**Primary Dependencies**: `ze-memory`, `ze-automation`, `ze-workspace`, `ze-skills`,
`ze-agents` claims, and **Phase 137's evidence/learning contracts**  
**Storage**: Existing `memory_procedures` replaced or hard-cut to lifecycle-owned procedure
records plus an append-only admission/version/feedback history; raw SQL migration in the
owning package  
**Testing**: pytest with mocked asyncpg and no real LLM; source-path, lifecycle transition,
migration, and process-local recovery tests  
**Target Platform**: Backend and existing procedure retrieval/review surfaces  
**Project Type**: Cross-package lifecycle hard cut  
**Performance Goals**: Candidate creation is non-blocking where its source currently is
asynchronous; admission/retrieval does not add an LLM call to procedure use  
**Constraints**: No skill execution expansion, workspace-gate change, generic arbitration,
compatibility API, dual-write, or dual-read

## Constitution Check

| Principle | Check | Result |
|---|---|---|
| I. Spec-First | Spec 138 defines lifecycle and exclusions | PASS |
| II. Single-User | No tenancy change | PASS |
| III. Layered Package Architecture | Lifecycle belongs with `ze-memory` as custodian; automation/workspace/skills submit candidates through SDK contracts; no plugin imports engine internals | PASS |
| IV. Typed, Explicit Python | Dataclasses/enums and typed errors; Phase 137 evidence/learning types are reused | PASS |
| V. Test Discipline | Unit tests mock stores and clients; transition invariants have dedicated tests | PASS |
| VI. Explicit Persistence | One owning migration chain; immutable history is explicit | PASS |
| VII. One LLM Gateway | Existing extractors may remain callers; no new model gateway | PASS |
| VIII. Pre-v1 Hard Cuts | Remove public writer and dream direct INSERT in the same migration phase | PASS |

**Post-design re-check**: A source-specific adapter is permitted only to translate its completed
record into the common candidate; it cannot persist or approve directly. This retains one door.

## Project Structure

### Documentation

```text
specs/phases/138-procedure-lifecycle/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── contracts/procedure-admission.md
├── quickstart.md
├── tasks.md
├── checklists/requirements.md
└── .spec-context.json
```

### Proposed Source Areas

```text
core/cognition/ze-memory/ze_memory/
├── procedures/types.py              # lifecycle values
├── procedures/store.py              # private persistence/query contract
├── procedures/admission.py          # sole governed write path
├── procedures/retrieval.py          # active-version retrieval
└── migrations/versions/zm0xx_*.py

core/automation/ze-automation/ze_automation/
├── goals/executor.py                # candidate + provisional resolution
└── workflow/...                     # completed workflow candidate

core/ops/ze-workspace/ze_workspace/  # approved-run candidate adapter
core/automation/ze-skills/ze_skills/ # imported-skill candidate adapter
core/cognition/ze-memory/ze_memory/dream/promoter.py
packages/ze-sdk/ze_sdk/memory.py
```

**Structure Decision**: `ze-memory` owns the lifecycle because procedures are reusable memory,
not execution plans. Source packages expose only candidate submission. Phase 137 remains the
owner of evidence and learning vocabulary; this phase stores references to it rather than
creating parallel evidence tables.

## Complexity Tracking

None. The feature is broad but has one lifecycle boundary and explicit source adapters.
