# Derivation and State-Lifetime Requirements Checklist: AgentContext Derivation

**Purpose**: Unit tests for the requirements of phase 200's refactor-safety areas: inheritance rules, pause and checkpoint behaviour, merge semantics, and plugin extension declarations. For the spec reviewer and the build lanes.

**Created**: 2026-10-26

**Feature**: [spec.md](../spec.md) · [plan.md](../plan.md) · [data-model.md](../data-model.md)

Evaluated by the Spec Architect on 2026-10-26. A ticked item passed. The note names where it is answered, or the edit made to answer it.

## Requirement Completeness

- [x] CHK001 Is an inheritance rule required for every `AgentContext` field and every kind of derivation, with no field left implicit? [Completeness, Spec §FR-002, SC-002] — data-model.md gives the 31×4 table, and FR-002 makes a missing row a test failure.
- [x] CHK002 Are the runtime handles that never come from the parent named, along with where each kind gets them? [Completeness, Spec §Assumptions] — research R5 (`RuntimeHandles`, read from config); data-model.md "G (runtime)".
- [x] CHK003 Are requirements stated for the minimal undo and screen-action contexts, not only the three turn-related kinds? [Completeness, Spec §FR-001, Edge Cases] — FR-001 amended (analyze F6) to name the action kind.
- [x] CHK004 Is every `AgentState` key given a lifetime, including the keys that are supplied rather than reset (`prompt`, `session_id`, the input modality fields)? [Completeness, Spec §FR-006] — FR-006 amended (analyze F3); data-model.md lifetime table.
- [x] CHK005 Is the fate of each of today's unreset keys stated, one by one? [Completeness, Spec §FR-008] — FR-008 lists the four reset keys and the deleted `procedure_matches`; `compaction_span` is noted as cut by phase 198.

## Requirement Clarity

- [x] CHK006 Is "inherit" defined for `extensions`: copy or merge, and which keys a kind adds? [Clarity, Spec §FR-004] — FR-004, plus the contract's guarantee that mutating a child's `extensions` never changes the parent's.
- [x] CHK007 Is "one unit" for the write-gate part clear about which sub-fields a derivation may still set per child (resume inputs, `loop_active`)? [Clarity, Spec §FR-011] — FR-011 amended: resume inputs per subtask; `loop_active` always starts `False`.
- [x] CHK008 Is "run-scoped" defined, and is its difference from "thread-scoped" stated? [Clarity, Spec §FR-014, Key Entities] — the Field lifetime entity is amended. In the reset generator both are left out; `Run` documents the workflow ownership.
- [x] CHK009 Is "per turn across subtasks" for the delegate caps precise about concurrency, given that subtasks run at the same time? [Clarity, Spec §FR-013] — research R7 (one shared tally per pass; no await between the check and the bump).

## Requirement Consistency

- [x] CHK010 Does the delegate reset list in FR-012 agree with the delegate column of the data-model table, field by field? [Consistency, Spec §FR-012] — yes. The table also resets `tool_calls`, `sources`, `model` and `conductor` (each with a reason), which FR-012 does not forbid.
- [x] CHK011 Are the behaviour changes FR-010 allows consistent with the ones the plan makes? [Consistency, Spec §FR-010] — FR-010 amended (analyze F1).
- [x] CHK012 Is the Child run outcome entity consistent with what the merge needs (whole ledger per subtask, shared tally)? [Consistency, Spec §Key Entities] — amended (analyze F7).
- [x] CHK013 Do SC-001 and the Undo edge case agree on where the minimal constructions live? [Consistency, Spec §SC-001] — both now say they go through the owner.

## Scenario Coverage: pause, resume and checkpoints

- [x] CHK014 Are requirements stated for conductor state across a confirmation pause, including that a resumed delegate is not counted twice? [Coverage, Spec §US2 scenario 3] — US2-3, plus the new edge case "A pause in the middle of a subtask".
- [x] CHK015 Is the procedure invocation's fate across a pause specified? [Coverage, Spec §Edge Cases] — the new pause edge case: completed after the resume.
- [x] CHK016 Does the spec or plan say what happens to a turn paused before the upgrade, whose checkpoint holds the old context shape? [Coverage, Gap → Plan §Constitution VI] — plan Constitution VI: the context is revived as `None`, the turn answers "Missing routing envelope or agent context", and there is no shim (pre-v1 hard cut). The spec has no requirement here, by design.
- [x] CHK017 Is the case of two subtasks invoking procedures in one turn resolved, including what the single trace field shows? [Coverage, Spec §Edge Cases] — the edge case states the lowest subtask index.

## Edge Case Coverage

- [x] CHK018 Is the image-turn first message covered by the subtask derivation? [Edge Case, Spec §Edge Cases "Image turns"] — `messages` is Given from `_build_messages`.
- [x] CHK019 Is `retry_mode` reaching delegates and subtasks a requirement, not only an assumption? [Edge Case, Spec §Edge Cases "Retry runs", FR-011] — part of the write-gate unit inherited by both.
- [x] CHK020 Are the conductor's run-local values (soft deadline, stall details) kept from leaking into a delegate through inherited `extensions`? [Edge Case, Spec §Edge Cases "Conductor run state"] — the edge case was added during planning (research R3).
- [x] CHK021 Is the workflow cancel path covered by the generated step reset? [Edge Case, Gap → research R9] — R9: the reset also applies on cancel and is harmless; T034 covers it.

## Plugin Extension Declarations

- [x] CHK022 Is it required that a plugin state field with no lifetime fails at startup, and that the error names the field? [Completeness, Spec §FR-007, US3 scenario 3] — yes.
- [x] CHK023 Is it specified how a plugin declares lifetimes without importing engine packages? [Dependency, Spec §FR-007 → Plan §Constitution III] — the plan sets the markers in ze-agents, re-exported via `ze_sdk.types`. The spec leaves the mechanism to the plan, which is acceptable.
- [x] CHK024 Are the workflow extension's fields named with their lifetime, so FR-014's "run-scoped" is checkable? [Measurability, Spec §FR-014] — data-model.md lists all ten as `Run`.

## Acceptance Criteria Quality

- [x] CHK025 Can SC-004 ("exactly one place for inheritance") be checked objectively? [Measurability, Spec §SC-004] — yes: the derivation table in `derive.py` is the only inheritance edit. The table test (SC-002) fails if a field is added without it.
- [x] CHK026 Does SC-005 name each routing path that needs a test? [Measurability, Spec §SC-005] — single, compound, delegate, milestone (T015, T027, T029).

## Dependencies and Assumptions

- [x] CHK027 Is the dependency on phase 198's patches and their regression tests stated and protected? [Assumption, Spec §Assumptions] — analyze F4 added explicit keep-the-test notes to T017, T024, T028 and T029.
- [x] CHK028 Are the seams later phases (201, 208, 209, 214) rely on named? [Dependency → Plan §Seams] — the plan's "Seams for later phases" table.
