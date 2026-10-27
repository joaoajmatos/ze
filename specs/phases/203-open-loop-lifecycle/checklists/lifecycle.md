# Lifecycle Atomicity and Concurrency Checklist: Open-Loop Lifecycle

**Purpose**: Test the requirements for event atomicity, state guards, races, fingerprints and the 202 hand-off before implementation starts (author-run gate).
**Created**: 2026-10-26
**Feature**: [spec.md](../spec.md) · [data-model.md](../data-model.md) · [research.md](../research.md)

Items are ticked when the artifacts answer them; the answer's location follows the arrow.

## Requirement Completeness

- [x] CHK001 - Is "atomic" defined per event as the exact set of rows and tables written in its one transaction? [Completeness, Spec §FR-002] → data-model.md "Events and rules", last column
- [x] CHK002 - Is the outcome for every (event, starting state) pair specified, including the create events' target states? [Completeness, Spec §FR-003, SC-004] → data-model.md table; contracts/lifecycle-events.md `EVENT_RULES`
- [x] CHK003 - Are all fourteen events named consistently across spec, data model and contract? [Completeness, Spec §FR-001] → FR-001, data-model.md, `LoopEvent`
- [x] CHK004 - Is the declared stamp's full field set (confidence, `confirmed_at`, deadline, rationale) defined once, with the window source for each user? [Completeness, Spec §FR-004] → data-model.md "The declared stamp"; research R3
- [x] CHK005 - Is it specified which evidence the drop and expire fingerprints hash (all of the loop's evidence links at the moment of the event)? [Completeness, Spec §FR-006] → data-model.md DROP row
- [x] CHK006 - Is the fingerprint of a loop with no evidence defined, separately for drop and expire? [Edge Case, Gap] → data-model.md "Fingerprint of an empty evidence set" (added by this checklist; split for expire after review)

## Requirement Clarity

- [x] CHK007 - Is the difference between a refused event (raises) and a no-change event (returns without writing) defined, and tied to the REST 409? [Clarity, Spec Edge Cases] → data-model.md, paragraph after the table
- [x] CHK008 - Does the decay-after-sweep requirement say which rationale and state survive? [Clarity, Spec US1-3] → data-model.md DECAY row (D: confidence only); research R2
- [x] CHK009 - Is the losing promoter's write specified (source row kept with `promoted = false`, no confidence write)? [Clarity, Spec Edge Cases] → data-model.md PROMOTE row; research R10
- [x] CHK010 - Is the drift deadline guard stated as re-checked at write time, not only at candidate read? [Clarity, Spec US1-3] → research R2
- [x] CHK011 - Is "returns the loop as stored" defined as the row read back in the same transaction, never patched in Python? [Clarity, Spec §FR-002] → contracts/lifecycle-events.md "Behavior every method guarantees"

## Requirement Consistency

- [x] CHK012 - Are the FR-003 move rules (A→D, D→A, S→C, S→A) consistent between spec, data model and the table test task? [Consistency, Spec §FR-003] → FR-003, data-model.md "Rules the table states", tasks T001
- [x] CHK013 - Is the promote confidence rule (`GREATEST(c, 0.7)`) consistent with FR-004's "defined once" stamp? [Consistency, Spec §FR-004] → research R3 (one fragment, confidence expression as a parameter)
- [x] CHK014 - Do the log event names in the contract match what existing tests read? [Consistency] → contracts/lifecycle-events.md "Logs once" (names kept; `PG/test_loop_resolve_pg.py`)

## Scenario Coverage (races and recovery)

- [x] CHK015 - Is the ordering between a drop and a concurrent evidence link defined, so the fingerprint cannot miss evidence linked in the same instant? [Coverage, Gap] → research R2 "Row lock first" (added by this checklist)
- [x] CHK026 - Is decay's computed confidence specified as read under the row lock, so two concurrent decays compose? [Coverage, Gap] → research R2; data-model.md DECAY row (added after review)
- [x] CHK016 - Are expire-vs-confirm and promote-vs-drop races defined? [Coverage] → data-model.md EXPIRE row (A: no change), PROMOTE row (X: refused) and contracts/inflow-commit.md (`Corroborator` never raises)
- [x] CHK017 - Is recovery after a failed event specified (nothing kept, error to the caller; fire-and-forget commit logs and never raises)? [Recovery, Spec §SC-001, §FR-010] → contracts/lifecycle-events.md "Atomic"; research R7
- [x] CHK018 - Is it stated that collision detection cannot roll back a committed create? [Exception Flow] → research R5 (detection runs fire-and-forget after the writer, `ze_collision/detect.py:175-190`)
- [x] CHK019 - Is a stale expiry specified to block resurfacing exactly like a user drop? [Coverage, Spec Edge Cases, §SC-005] → data-model.md EXPIRE row; SC-005

## Non-Functional Requirements

- [x] CHK020 - Is it required that no model, embedding or network call runs inside an event's transaction (so row locks stay short)? [Non-Functional, Gap] → research R2 "No I/O inside a transaction" (added by this checklist)
- [x] CHK021 - Is one clock (the database's `now()`) specified for every stamp? [Consistency, Spec §FR-004] → research R3

## Dependencies and Assumptions (the 202 hand-off)

- [x] CHK022 - Are the landing order and the per-file hunk split with 202 documented in this plan, and recorded as mirrored in 202's? [Dependency] → plan.md "Coordination with 202"
- [x] CHK023 - Is the owner of the commit vocabulary (`loop_judge.DecisionKind`) stated the same way in spec, plan and research? [Consistency, Spec Assumptions] → spec Assumptions, plan.md, research R6
- [x] CHK024 - Is responsibility for the rebase onto 202 assigned to one lane with a task? [Dependency] → plan.md Lane Plan rules; tasks T032, T037
- [x] CHK025 - Is the assumption that 199's resolve edge already exists verified against `main`? [Assumption, Spec Assumptions] → spec Context table, Resolve row (`store.py:272-320`)
