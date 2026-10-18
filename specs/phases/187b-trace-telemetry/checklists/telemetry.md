# Telemetry Requirements Checklist: Trace Telemetry (187b)

**Purpose**: check that the measurement requirements are complete, unambiguous and testable before implementation.
**Created**: 2026-10-18
**Feature**: [spec.md](../spec.md)

## Completeness

- [x] CHK001 Is every graph stage named, including the six with no frame today? [Completeness, Spec §FR-002]
- [x] CHK002 Is the turn total defined, including whether confirmation waits count? [Clarity, Spec US2-1, Data model `paused_ms`]
- [x] CHK003 Is "main model" defined for single, tiered and compound turns? [Clarity, Plan §Node wrapper]
- [x] CHK004 Is context fill defined (largest prompt / window) with a fallback window? [Clarity, Clarification Q3, Spec US2-4]
- [x] CHK005 Is the bar recorded per question for every surface that writes trace rows? [Coverage, Plan bar maps, T011]
- [x] CHK006 Is how live and committed tool rows are matched defined for parallel subtasks? [Edge Case, Spec §FR-007]

## Honesty and failure

- [x] CHK007 Is it stated that telemetry never fails or delays a turn, with a test? [Spec §FR-008, T005, T008]
- [x] CHK008 Is a restart during a confirmation wait handled honestly (partial flag)? [Edge Case, Spec Edge Cases]
- [x] CHK009 Are estimates (unknown price or window) marked rather than blanked? [Spec US2-4]
- [x] CHK010 Is post-reply background work excluded from the turn's numbers? [Edge Case, T006]

## Consistency

- [x] CHK011 Is the rename applied to every reader (types, store, REST, WS, seed, web)? [Consistency, Plan Blast radius, quickstart grep]
- [x] CHK012 Do old traces (before 187b) have a defined read behaviour on server and web? [Edge Case, T002, T013]

## Measurability

- [x] CHK013 Is the overhead bound (SC-004) measured by a named task? [Measurability, T014]
- [x] CHK014 Is "no client arrival timing" checkable by a test? [Measurability, SC-006, T013]
