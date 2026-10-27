# Governor and Push Bar Requirements Checklist: Push Bar and Cooldowns

**Purpose**: Check that the requirements for the claim rule, the push bar and the moved records are complete, unambiguous and testable before the build lanes start. Items test the written requirements, not the code.
**Created**: 2026-10-26
**Feature**: [spec.md](../spec.md), [plan.md](../plan.md), [contracts/](../contracts/)

## Claim rule completeness

- [x] CHK001 Is the outcome of every governor path (cooling, over budget, held, delivered, persist error, push error, store error) mapped to a `PushOutcome` and to what happens to the claim? [Completeness, contracts/notifier.md "Outcomes and the claim", data-model.md state diagram]
- [x] CHK002 Is "once ever" (no window) defined, and are the callers that rely on it listed? [Clarity, research R3, contracts/notifier.md call-site table]
- [x] CHK003 Is it stated which push classes may, must and must not pass `once_per`? [Completeness, FR-009, contracts/notifier.md `notify` rules]
- [x] CHK004 Is the atomicity requirement (FR-006) backed by a mechanism precise enough to test a race? [Measurability, research R2, tasks T006 concurrent claim]
- [x] CHK005 Is the held-then-failed-release case decided? [Edge case, Clarifications Q2, FR-016]
- [x] CHK006 Is the store-failure behaviour (fail open) stated, with its log key? [Exception flow, spec Edge Cases, research R11]
- [x] CHK007 Are the cooldown keys and windows of all four FR-007 jobs written down with today's values? [Completeness, contracts/notifier.md "Cooldown jobs"]
- [x] CHK008 Is the cost of building a message before the cooldown check addressed? [Gap closed by research R9, `on_cooldown`]

## Push bar clarity

- [x] CHK009 Are the bar's inputs defined field by field, including which text novelty compares and which text grounding checks? [Clarity, data-model.md `PushCandidate`]
- [x] CHK010 Are the threshold values and their config keys stated per source, unchanged from main? [Consistency, data-model.md `BarThresholds` table, spec Assumptions]
- [x] CHK011 Is the order of conditions, and therefore the reported reason, defined? [Clarity, research R12]
- [x] CHK012 Is the change in hypothesis novelty (shared history, body against body) stated as a behaviour change, not left implicit? [Consistency, research R5]
- [x] CHK013 Is "built without NLI" defined as a construction-time, logged choice with no default? [Clarity, FR-004, research R10]
- [x] CHK014 Is SC-005 ("a new source needs only an adapter") testable? [Measurability, tasks T021 and T025]

## Records and boundaries

- [x] CHK015 Is SC-001's grep scope precise (which directories, which exclusions)? [Measurability, SC-001, quickstart.md section 3]
- [x] CHK016 Does every former `push_log` use have a named new owner or a deletion? [Coverage, spec Context items 1-5, research R4/R6/R7/R8]
- [x] CHK017 Are both migrations placed on their owners' chains with the next free revision on main? [Consistency, contracts/migrations-and-failures.md]
- [x] CHK018 Is the workflow-failure read defined for runs with no workflow? [Edge case, contracts/migrations-and-failures.md, `"unknown"`]
- [x] CHK019 Are the dependency-graph edge changes stated (ze-worldstate drops ze-correlation; ze-priority declares ze-proactive)? [Consistency, research R13]
- [x] CHK020 Are the loop re-push window and its config key stated with a default? [Completeness, FR-015, Clarifications Q1]

## Notes

- All items pass after the 2026-10-26 analyze fixes (see [analysis.md](../analysis.md)).
