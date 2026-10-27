# Behaviour Preservation Checklist: Judgment Surface

**Purpose**: Test whether the requirements pin down what must stay the same across the refactor: decisions, bars, trace shape and calibration verdicts.
**Created**: 2026-10-26
**Feature**: [spec.md](../spec.md)
**Audience**: reviewer (Vigil) and the lane engineers, before implementation.

Each item was answered by the architect against spec.md, plan.md, data-model.md, the contracts and tasks.md. A ticked item names where the answer lives.

## Requirement Completeness

- [x] CHK001 Is every surface whose decision must stay unchanged named, including the background ones? [Completeness, Spec §FR-012, Context table] — six surfaces plus the deleted `fact_judge` path; FR-012 covers all.
- [x] CHK002 Are the shipped bars and enabled flags that must stay unchanged identified by location? [Completeness, Spec §FR-012] — `config.yaml` `system_one.surfaces`; "What does not change".
- [x] CHK003 Is the trace row shape that must not change named, with its consumers? [Completeness, Spec Assumptions, data-model.md Trace rows] — `JudgmentTrace`/`JudgmentBar` unchanged; REST, `trace_update`, store, web.
- [x] CHK004 Are the per-runner rules that must survive calibration refactoring listed (spent sets, verdict marker, rerun, acceptance rules)? [Completeness, Spec §US3 scenario 2, contracts/calibration-harness.md Rules]
- [x] CHK005 Are the CLI flags that docs and the Makefile rely on required to keep their names? [Completeness, contracts/calibration-harness.md Rules]
- [x] CHK006 Is the checkpoint compatibility of the new record (it rides in `RoutingEnvelope`) addressed by a requirement or plan item? [Completeness, research R7, tasks T006]

## Requirement Clarity

- [x] CHK007 Is "unchanged decision behaviour" stated as a checkable rule rather than an intent? [Clarity, Spec §FR-012, §SC-005] — decision tests pass with only construction, import and patch-target edits.
- [x] CHK008 Is `skip_reason`'s single meaning defined for each case (raised, client skip, invalid, held, used)? [Clarity, Spec §FR-007, contracts/judgment-surface.md Skip reason by surface]
- [x] CHK009 Is "held under a bar" separated from "not used", with examples per surface? [Clarity, Spec §FR-007] — routing `abstain`, intake `hold`; research R5 corrects the earlier `abstain` example.
- [x] CHK010 Is "identical calibration output" defined precisely (byte-for-byte, which modes, how wall-clock lines are handled)? [Clarity, contracts/calibration-harness.md Golden checks]
- [x] CHK011 Is SC-004 free of a line target, with the structural check named? [Clarity, Spec §SC-004] — no line-count target (user, 2026-10-27); each shared helper defined once in the harness, checked by T036's scan.

## Requirement Consistency

- [x] CHK012 Do the trace-row rules in data-model.md match today's `judgments_from_result` rules exactly, apart from the inputs? [Consistency, data-model.md Trace rows, Spec Edge Cases]
- [x] CHK013 Are routing, skills and complexity trace rows required to stay identical, so the only row change is the intake's new error rows? [Consistency, research R5 "Effect per surface", Spec §FR-006]
- [x] CHK014 Is the warn-once rule consistent with complexity's existing per-instance behaviour and with the tests that assert warnings? [Consistency, research R6, tasks T012/T021]
- [x] CHK015 Does the per-question bar map in data-model.md match the bar names the nodes use today (`nodes/routing.py:85-88`, `nodes/skills.py:58-61`, `nodes/tier.py:83`, `judgment_bars._INTAKE_BARS`)? [Consistency, data-model.md Surface declarations]
- [x] CHK016 Is the gate order (disabled, uncalibrated, unavailable) consistent with each surface's current outcome labels (`off`, `uncalibrated`, `fallback/<reason>`, E5 fallback)? [Consistency, contracts/judgment-surface.md Call sites]

## Scenario and Edge Case Coverage

- [x] CHK017 Is the "not asked" case (off, uncalibrated, no client, surface precondition) required to produce no record and no rows, as today? [Coverage, Spec Key Entities, US1 scenario 3]
- [x] CHK018 Is the missing-answer-on-ok case covered? [Edge Case, Spec Edge Cases]
- [x] CHK019 Is the corroboration consistency rule (`corroborate_hold <= promote_hold`) carried into the shared calibrated rule? [Edge Case, Spec Edge Cases, data-model.md]
- [x] CHK020 Is the invalid-bar case's behaviour (unset, uncalibrated, logged once) specified? [Edge Case, Spec Edge Cases]
- [x] CHK021 Is the loop-suppression case (reminder or goal created this turn) required to keep all six rows? [Edge Case, Spec Edge Cases]
- [x] CHK022 Is the `loop_gate.py:536` breakage acknowledged as the one calibration path with no golden baseline, with its own requirement? [Coverage, research R14–R15, tasks T028]

## Dependencies & Assumptions

- [x] CHK023 Is the hunk split with floor 203 recorded for every shared file, with a landing order? [Dependency, plan.md Coordination with 203]
- [x] CHK024 Is the assumption that `decide()` functions stay untouched consistent with 203 changing `IntakeOutcome` loop kinds later? [Assumption, Spec §FR-009, plan.md Coordination] — 202 changes no decision kinds; 203 owns that change and its tests.
- [x] CHK025 Is the "no live calibration" assumption backed by an offline method that exercises the live code path? [Assumption, Spec Assumptions, research R14]

## Notes

- No open item. Re-run this checklist if 203's rebase changes a decision kind that a 202 golden file prints (203 edits only kind-string literals in the runners).
