# Feature Specification: Open-Loop Lifecycle

**Feature Branch**: `203-open-loop-lifecycle`

**Created**: 2026-10-22

**Status**: Draft

**Depends on**: 199 (landed), which added the `suspected → closed` resolve edge as `LoopStore.resolve` (`suspected-loop-resolution.md`) and a loop's claim kind derived from its state (`loop-claim-kind-from-state.md`). 202 (judgment surface) also edits `admission.py`, `intake.py`, `commitment_judge.py`, `loop_judge.py`, `corroboration.py` and `nodes/memory.py`: 202 lands first and this phase rebases onto it. The hunk split is in plan.md, "Coordination with 202".

**Input**: Architecture review 2026-10-22, candidate C7 plus the loop-inflow commit (cognition #5): "A lifecycle module whose interface is the domain events (create declared/suspected, confirm, track, corroborate, promote, resolve, drop, decay, drift); each event is atomic; transition and stamp rules live inside it; the store shrinks to rows and queries; the closure and the 16-parameter threading are removed; one decision vocabulary; tests against test-pg. Hypotheses and suspected loops stay separate concepts."

## Context

An **open loop** moves through `suspected → active → drifting → closed | dropped` (glossary). The store owns which moves are legal (`ze_worldstate/store.py:26-39`). Each domain event, though, is put together by its caller from two or three separate store writes. None of these writes share a transaction.

| Event | Today | File |
|---|---|---|
| Confirm | `transition(ACTIVE)` (stamps `confirmed_at`), then `stamp_declared` (stamps confidence, deadline, rationale and `confirmed_at` again), then fields patched by hand | `review.py:16-33` |
| Drop | `list_evidence`, `transition(DROPPED)`, then `set_dismissed_evidence_fingerprint`. If the run fails between the last two, the fingerprint is lost and the same evidence can bring the loop back | `review.py:41-53` |
| Decay | `set_confidence`, `transition(DRIFTING)`, `set_drift_rationale`. The state check reads the loop from before the decay | `decay.py:38-57` |
| Drift sweep | `transition(DRIFTING)`, then `set_drift_rationale` | `jobs/drift_sweep.py:26-32` |
| Stale suspicion | `transition(DROPPED)`, no fingerprint | `jobs/stale_suspicion.py:31` |
| Declared create (inflow) | contribution + `create`, `set_drift_deadline`, evidence and entity links, origin source. The contribution omits the evidence the suspected path includes | `extraction.py:349-375` |
| Suspected create (inflow) | contribution + `create`, then evidence and entity links, then origin source, each a separate write | `extraction.py:459-480` |
| Declared create (`track_loop`) | contribution + `create` with no existence checkers, then `stamp_declared`, then entity links. No evidence, no origin source | `tracking.py:124-152` |
| Track: confirm, reinforce or revive | `set_confidence`, or `transition(ACTIVE, user_asked=...)` then `stamp_declared` | `tracking.py:90-108` |
| Note evidence (170) | evidence links, entity links, then `record_corroboration` (moves an active loop's deadline), each a separate write | `extraction.py:204-240` |
| Corroborate / promote (172) | evidence links, `add_source`, then `promote` (one statement) and `mark_source_promoted`, or `set_confidence` | `corroboration.py:166-199`, `store.py:564-585` |
| Resolve | `find_matching_loop`, then `resolve` (199: one transaction, but a store method that holds a lifecycle rule) | `extraction.py:378-399`, `store.py:272-320` |
| Close (user) | `transition(CLOSED)` from active or drifting (REST, page, `close_loop` tool) | `review.py:36-38` |
| Link a reminder or goal | `link`, guarded by the live states (173) | `intake.py:347-367`, `store.py:425-447` |

The "declared stamp" rule (confidence 0.9, a fresh 7-day drift window, rationale cleared) is restated four times: `review.confirm_loop`, `tracking._stamp`, `extraction` (through `compute_drift_deadline`) and `promote(window_days=7)`. The comment at `store.py:24-25` says only drift and decay move a loop from active to drifting. The table does not enforce that; any caller can make the move.

The commit path for a loop that was admitted is shallow:

- `LoopInflow` (`admission.py:30-56`) holds eleven dependencies. `commit_for` (`admission.py:93-120`) builds a closure that passes them all back to the free function `propose_loop_candidates`, which takes 16 parameters (`extraction.py:550-568`).
- That function threads them on into `_commit_admitted` (16 parameters, `extraction.py:483-500`), then into `_create_declared_loop` (15) and `_create_suspected_loop` (14). `corroborate_match` takes 11 more, including a `link` closure (`corroboration.py:81-94`).
- `LoopAdmission.commit` is a mutable callable attribute, and `source` is set after the record is built (`admission.py:70`, `intake.py:198`).
- The decision type makes a round trip. `IntakeOutcome` kinds are remapped by string to `LoopGateDecision` kinds (`intake.py:45-49`), and `loop_judge.DecisionKind` lists `create_declared`, which only that remap produces.
- `propose_loop_candidates` still has a `provenance == "user_declared"` branch (`extraction.py:588-605`) that no caller reaches: `track_loop` uses `LoopTracker`.

Unit tests mock the store, so ordering and atomicity bugs are not caught. `make test-pg` exists (phase 170).

### Blast radius

The loop-store mutations listed above have 26 production call sites plus 3 `create` sites, all in `ze_worldstate` (`review.py`, `decay.py`, `tracking.py`, `corroboration.py`, `extraction.py`, `intake.py`, `jobs/drift_sweep.py`, `jobs/stale_suspicion.py`; counted 2026-10-26). The real-Postgres tests in `apps/ze-api/tests/pg/` call the same write methods about 60 times for setup. plan.md lists the callers by package. The callers outside the package reach loops through:

- REST: `apps/ze-api/ze_api/api/v0/loops/router.py`, through `ze_worldstate/rest.py`;
- the `loops` agent tools in `ze_worldstate/agents/`;
- the inflow wiring in `ze_worldstate/inflow.py` and `bootstrap.py`;
- the commitment intake in `intake.py`, and `write_memory` (`ze_core/orchestration/nodes/memory.py:197-200, 292-300`), which runs the loop commit fire-and-forget;
- the contradiction hook in `apps/ze-api/ze_api/wiring/hooks.py:43-48`, which calls the decay cascade;
- the trace: the `intake_outcome` row carries the intake kind strings, which ze-web maps to sentences (`apps/ze-web/src/widgets/assemble/lib/instruments/judgments.ts:84-86`);
- the calibration runners `eval/calibration/commitment_intake.py` and `loop_gate.py`, which read the kind strings and import the 109 gate from `extraction.py`.

## Clarifications

### Session 2026-10-26

- Q: The commitment intake names its loop outcomes `resolve_loop` / `create_loop_declared` / `create_loop_suspected`, and the trace and ze-web read those strings. Rename them to the shared commit vocabulary, or keep them? → A: Rename to `resolve` / `create_declared` / `create_suspected`. ze-web's `judgments.ts` map is updated with the same sentences. No alias for old stored traces (pre-v1 hard cut).
- Q: `track_loop` runs before the turn's episode exists, so it has no evidence to link. Link the episode after the turn, or not? → A: Defer. `track_loop` goes through the same declared-create event with no evidence plus an origin source (conversation, thread id). Linking the turn episode to a tracked loop later is out of scope.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A loop is never left half-changed (Priority: P1)

The user drops a suspected loop on World. Later, the same email evidence arrives again. The loop does not come back. This holds even if the process stopped in the middle of the drop.

**Why this priority**: A dropped loop that comes back, or a confirmed loop with a stale deadline, breaks the user's trust in Needs you. Today both can happen, because each event is several separate writes.

**Independent Test**: Against a real Postgres (test-pg), make the second write of each event fail. The loop is either fully moved, with all its fields, or not moved at all.

**Acceptance Scenarios**:

1. **Given** a suspected loop with evidence, **When** the user drops it, **Then** its state, `closed_at` and dismissed-evidence fingerprint are written together, and the same evidence later creates no loop.
2. **Given** a suspected loop, **When** the user confirms it (page, REST or chat), **Then** state, confidence 0.9, `confirmed_at`, the 7-day drift deadline and the cleared rationale are written together, and the returned loop matches the stored row.
3. **Given** an active loop whose only evidence is contradicted, **When** decay runs, **Then** the new confidence, the move to `drifting` and the rationale are written together. A loop that the sweep drifted a moment earlier is not drifted a second time.

---

### User Story 2 - Every way into and out of a loop follows the same rules (Priority: P1)

The user says "keep an eye on the budget for Ana" (`track_loop`). An email also proposes a declared loop. Both paths create the loop with the same stamp: confidence, deadline, evidence links and origin source. A matching loop is confirmed, reinforced or revived by the same rules wherever the match comes from.

**Why this priority**: The two declared-create paths differ today in evidence and origin source. The stamp rule is restated in four places.

**Independent Test**: A table test over every lifecycle event and every starting state. It checks which moves are allowed, what each move stamps, and that only drift and decay move a loop from active to drifting.

**Acceptance Scenarios**:

1. **Given** no matching loop, **When** `track_loop` creates one, **Then** it goes through the same declared-create event as an inflow: the declared stamp, entity links and an origin source for the conversation thread. It passes no evidence, because the turn's episode does not exist yet (Clarifications 2026-10-26).
2. **Given** a drifting loop, **When** the user explicitly asks to keep it in mind, **Then** it is revived. **When** the REST confirm route, decay or the sweep act on it, **Then** they cannot revive it.
3. **Given** a suspected loop, **When** a turn or an email says it is done, **Then** it moves to `closed` with the resolving evidence recorded (199's edge), and no error is swallowed.
4. **Given** any caller other than drift or decay, **When** it asks to move an active loop to drifting, **Then** the move is refused.

---

### User Story 3 - An admitted loop is committed by one method with one decision (Priority: P2)

A maintainer reads how an admitted loop becomes a row. One loop-inflow module holds its dependencies and exposes one commit method. That method takes a commit decision (resolve, create declared, create suspected), the text, inflow, evidence and source. The System One gate and the Haiku fallback both produce that decision.

**Why this priority**: It removes the closure, the parameter threading and the round trip between decision types. It also makes the commit that `write_memory` fires and forgets a plain call that can be tested.

**Independent Test**: The commit method, called with each decision against test-pg and a fake title writer, produces the expected loop rows. No closure is involved.

**Acceptance Scenarios**:

1. **Given** a create-suspected decision with evidence, **When** it is committed, **Then** one suspected loop with that evidence and an origin source exists.
2. **Given** the Haiku fallback path, **When** it decides to create, **Then** it produces the same decision type and goes through the same commit method.

---

### Edge Cases

- **Two inflows corroborate the same suspected loop at once.** Only one promotion wins. The other records its source row as a corroboration and does not promote twice (guarded by state, as today).
- **The title writer returns nothing.** The commit writes nothing and reports why.
- **A resolve matches no live loop.** Nothing changes, and it is reported as "no match", not as an error.
- **A stale-suspicion expiry.** It is a drop that records a fingerprint, so an expired hunch does not come straight back from the same evidence.
- **A confirm on a loop that is already active.** It is refused with the same typed error the REST route maps to 409 today.
- **Decay on a closed or dropped loop.** Confidence may change, but the state never moves.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: One lifecycle module MUST own every open-loop event: create declared, create suspected, confirm, track (confirm / reinforce / revive), note evidence (170), corroborate, promote, resolve, close (user), drop, expire (stale suspicion), link a reminder or goal, decay from evidence, and drift from absence.
- **FR-002**: Each event MUST be atomic. It is one statement, or one transaction across the loop row, its evidence and entity links and its source rows. It returns the loop as stored.
- **FR-003**: Which moves are legal, and who may make each one, MUST live inside the lifecycle module:
  - only drift and decay may move a loop from active to drifting;
  - only an explicit user request may revive a drifting loop;
  - only the resolve event may move a loop from suspected to closed (199);
  - only promote, confirm and track may move a loop from suspected to active.
- **FR-004**: The declared stamp (confidence 0.9, a fresh drift window, rationale cleared, `confirmed_at` set) MUST be defined once, and confirm, track, declared create and promote all use it. Promote keeps its own rule, `GREATEST(confidence, 0.7)` (phase 172).
- **FR-005**: The two declared-create paths (an inflow, and `track_loop`) MUST record the same things: evidence on the contribution, evidence links, entity links, and an origin source when one is known.
- **FR-006**: Drop and stale-suspicion expiry MUST record the dismissed-evidence fingerprint in the same atomic write as the state change.
- **FR-007**: The loop store MUST shrink to row reads and writes plus queries. It exposes no method that changes state, confidence, deadline, rationale or fingerprint on its own, outside a lifecycle event.
- **FR-008**: One loop-inflow module MUST hold its dependencies and expose one commit method. The method takes a commit decision, the text, inflow, evidence and source.
  - `commit_for`, the mutable `LoopAdmission.commit` attribute, and the parameter threading through `propose_loop_candidates`, `_commit_admitted` and `_create_*_loop` are removed.
- **FR-009**: One commit-decision vocabulary MUST exist: resolve, create declared, create suspected, hold, fallback.
  - The commitment intake, the System One loop gate and the Haiku 109 gate all produce it.
  - The string remap `_LOOP_KIND` (`intake.py:46-50`) is removed.
- **FR-010**: `write_memory` MUST still commit loops fire-and-forget, after the episode is written. It calls the inflow's commit method directly.
- **FR-011**: Hypotheses (ze-correlation) and suspected loops MUST stay separate concepts and separate stores. This phase changes no hypothesis code.
- **FR-012**: Every lifecycle event MUST have a test against a real Postgres, marked `pg` and run by `make test-pg`. The existing mocked-store tests may stay only where they test logic other than the store.
- **FR-013**: Behaviour seen through REST, the `loops` agent tools, the World page and the trace MUST be unchanged, except for:
  - the atomicity fixes;
  - the declared-create alignment (FR-005);
  - the fingerprint on stale expiry (FR-006);
  - the intake outcome kind strings on the trace, renamed to the commit vocabulary (Clarifications 2026-10-26);
  - a promote that loses a race no longer lowers the winner's confidence (research R10).

### Key Entities

- **Open loop**: one item of unfinished business, with state, confidence, drift deadline, rationale, evidence, entities and source rows.
- **Lifecycle event**: one named change to an open loop that the domain recognises (confirm, drop, resolve, and so on). It applies completely or not at all.
- **Commit decision**: what an inflow decided to do with a text: resolve, create declared, create suspected, hold, or fall back.
- **Origin source**: the inflow and reference that first produced a loop, used by corroboration's independence rule.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With the second write of each event forced to fail on test-pg, 100% of events leave the loop fully unchanged or fully changed.
- **SC-002**: The declared stamp is defined in exactly one place (today four).
- **SC-003**: No function or method that a commit calls takes more than 8 parameters (today up to 16). Constructors, which receive injected dependencies, are not counted. The commit closure is gone.
- **SC-004**: Every lifecycle event has at least one real-Postgres test, and the transition table test covers every (event, starting state) pair.
- **SC-005**: A dropped loop is never brought back by the same evidence, including after a stale expiry, across a 30-day replay of the seed fixtures.

## Assumptions

- **What 199 has already landed.** 199 lands the resolve edge and the derived claim kind first. This phase moves them into the lifecycle module and does not decide them again.
- **The store protocol.** The `LoopStore` protocol keeps its row and query methods for readers (REST lists, matching, surfacing). Its write surface becomes the lifecycle module's private implementation.
- **No migration.** Atomicity comes from transactions and single statements on the existing tables.
- **202's ownership.** 202 edits the judgment fields of `LoopAdmission` and the call in `admission.py`; this phase edits the commit side of the same files. The lane plan assigns `admission.py` to one lane, and the other lane rebases onto it.
- **Pre-v1 hard cut** (constitution Principle VIII). Removed store methods and the closure are deleted, not wrapped.
