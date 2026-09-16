# Feature Specification: Parallel Per-Subtask Gates

**Feature Branch**: `158-parallel-subtask-gates`

**Created**: 2026-09-16

**Status**: Implemented

**Input**: User description: "Spec the parked item after 151–157: per-subtask gate on independent parallel graph fan-out. Strictest-wins currently holds every specialist in a compound turn to the strictest decision. After 155, mixed gather+act is conductor (152 already gates those). Remaining graph parallel is independent multi-read (usually all allowed) and independent act+act (or any compound still on gather+synthesize). Split gates so a job that needs approval does not block a job that does not. Confirmations stay request_id-keyed (113). Do not restore sequential compound execute. Do not change conductor/152. Do not promote. Procedures out."

**Governed by**: [`specs/arch/companion-conductor-roadmap.md`](../../arch/companion-conductor-roadmap.md), [`specs/arch/pre-v1-hard-cuts.md`](../../arch/pre-v1-hard-cuts.md), [`specs/arch/ze-doctrine.md`](../../arch/ze-doctrine.md), graph compound [`005-orchestration`](../005-orchestration/spec.md), per-delegate gates [`152-per-delegate-gate`](../152-per-delegate-gate/spec.md), mixed rewrite [`155-mixed-gather-act-conductor`](../155-mixed-gather-act-conductor/spec.md), confirmation keying [`113-hardening-sweep`](../113-hardening-sweep/spec.md).

**Depends on**: 155 so mixed gather+act is already companion-primary; this phase only changes envelopes that **remain** `is_compound` and not sequential (independent fan-out + synthesize). 152/113 for confirmation semantics to copy onto graph subtasks.

**Does not start**: Restoring `_execute_compound` sequential; changing conductor rewrite; stall/promote; procedures; swarm.

---

## Overview

Independent parallel work still uses one capability decision for the whole turn: the strictest specialist wins. A write that needs approval therefore holds a lookup (or another write that would have been allowed) that was supposed to run beside it. Mixed research-then-email already goes to the conductor after 155. What remains is true fan-out: several independent jobs in one utterance that are **not** rewritten to companion.

This phase evaluates each of those jobs on its own specialist and intent. Allowed jobs run now. Jobs that need approval wait with their own confirmation. Jobs that are blocked or draft-only follow that specialist’s rule without forcing the others to wait. The user still gets one synthesized reply from the jobs that actually finished. Conductor turns stay on 152. Sequential graph execute stays deleted.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An allowed job is not held for a neighbor’s approval (Priority: P1)

The user asks two independent things in one message that still fan out (for example two writes, or a leftover read+write that 155 did not rewrite). One specialist is allowed to run now. The other must wait for approval. The allowed job runs. The waiting job does not. After the user approves that waiting job’s confirmation, it runs. The lookup or allowed write is not delayed because the other needed a yes.

**Why this priority**: This is the parked hole. Strictest-wins is the bug.

**Independent Test**: Compound envelope, sequential false, two specialists: one EXECUTE, one AWAIT_CONFIRMATION. After capability check, the EXECUTE specialist has run (or is runnable immediately) and the AWAIT specialist has not. A single overall AWAIT for the turn MUST NOT be the only decision.

**Acceptance Scenarios**:

1. **Given** independent parallel subtasks where specialist A evaluates EXECUTE and specialist B evaluates AWAIT_CONFIRMATION, **When** the turn executes, **Then** A runs without waiting for B’s confirmation.
2. **Given** B’s confirmation `request_id`, **When** the user approves, **Then** B runs and A is not re-run.
3. **Given** the user denies B, **When** the turn finishes, **Then** A’s result is still in the combined reply and B’s write did not happen.
4. **Given** a conductor (companion-primary) turn, **When** this phase ships, **Then** nested delegates still use 152 only; this split MUST NOT replace `run_delegate` gating.

---

### User Story 2 - Independent reads still fan out; one voice still answers (Priority: P1)

Two independent lookups (news and calendar, both allowed) still run together and synthesize. The user sees one answer. If every remaining parallel job is allowed, nothing extra waits. If one lookup were blocked, the other still runs and the combined reply does not pretend the blocked job succeeded.

**Why this priority**: All-read fan-out must not regress into conductor or into a serial confirm dance.

**Independent Test**: All-gather compound, sequential false, both EXECUTE → both run, synthesize as today. One BLOCKED + one EXECUTE → EXECUTE runs; synthesize uses only completed work.

**Acceptance Scenarios**:

1. **Given** independent multi-read, both EXECUTE, **When** the graph runs, **Then** both specialists still run in parallel and a single synthesized reply is produced.
2. **Given** one parallel subtask BLOCKED and one EXECUTE, **When** the graph runs, **Then** the EXECUTE job runs and the blocked job does not; the user is not told the blocked job succeeded.
3. **Given** two act-only specialists, sequential false, both AWAIT_CONFIRMATION, **When** the turn starts, **Then** neither write runs until its own confirmation is approved (two `request_id`s, not one shared hold that also blocks unrelated work — there is no EXECUTE neighbor).

---

### User Story 3 - Draft and blocked stay per specialist (Priority: P2)

A specialist whose mode is draft-only drafts; it does not force an allowed neighbor into draft. A blocked specialist fails that job only.

**Why this priority**: Strictest-wins today can turn a whole compound turn into DRAFT because one subtask is draft-only.

**Independent Test**: EXECUTE + DRAFT subtasks: EXECUTE runs for real; DRAFT runs as draft. EXECUTE + BLOCKED: as US2.

**Acceptance Scenarios**:

1. **Given** specialist A EXECUTE and specialist B DRAFT, **When** fan-out runs, **Then** A executes and B drafts (writes suppressed for B only).
2. **Given** spend over the session/day ceiling, **When** a parallel subtask is evaluated, **Then** that subtask is held to AWAIT_CONFIRMATION the same way 152 composes budget with the specialist decision — independently per subtask, not as one turn-wide min() that also freezes already-allowed neighbors after the fact.

---

## Edge Cases

- Single-specialist turns: one decision as today; this phase does not split them.
- Conductor rewrite (153/155): envelope is not compound fan-out; out of this phase.
- Resume after one of several confirmations: only that `request_id`’s specialist runs; other pending confirmations stay (113).
- Synthesize with a partial set: only completed subtask results; do not invent content for denied/blocked jobs.
- Empty subtask list: still blocked overall (existing safety).
- Abort: existing abort token still wins for in-flight EXECUTE jobs.
- Two EXECUTE jobs: still `asyncio.gather` (no extra serialisation).
- Haiku still marks mixed gather+act sequential-false: 155 should have rewritten; if a test envelope is still compound mixed, this phase is a **safety net** (read runs, write waits) — it does **not** replace 155’s conductor rewrite.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: For independent parallel compound (`is_compound` and not a conductor rewrite), the system MUST evaluate `CapabilityGate` (and spend budget, composed as in 152) **per subtask** specialist+intent. It MUST NOT take a single strictest `gate_decision` that holds every subtask.
- **FR-002**: Subtasks that evaluate EXECUTE MUST run without waiting for sibling AWAIT_CONFIRMATION, DRAFT, or BLOCKED decisions.
- **FR-003**: AWAIT_CONFIRMATION subtasks MUST pause that job only, persist confirmation by `request_id` (phase 113), and on approve run that specialist; deny MUST NOT run that write. Concurrent pending confirmations on one thread MUST stay isolated by `request_id`.
- **FR-004**: DRAFT subtasks MUST run in DRAFT; BLOCKED subtasks MUST NOT start a write. Neither MAY force an EXECUTE sibling into draft, confirmation, or block.
- **FR-005**: Synthesis MUST combine only completed subtask results. The user-facing reply MUST NOT claim a denied or blocked sibling succeeded.
- **FR-006**: Conductor turns and `run_delegate` MUST remain 152. This phase MUST NOT restore `_execute_compound` sequential, MUST NOT change 153/155 rewrite predicates, MUST NOT create procedures or promote to workflow/goal.
- **FR-007**: Single-agent turns MUST keep one gate decision as today.

### Key Entities

- **Parallel subtask decision**: The capability (and budget) outcome for one fan-out specialist, not for the whole envelope.
- **Partial compound result**: The set of `AgentResult`s from subtasks that actually ran (EXECUTE, DRAFT, or post-approve), used for synthesis.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of tested mixed-decision parallel fixtures run the EXECUTE specialist before the sibling confirmation is answered.
- **SC-002**: 100% of tested all-EXECUTE independent multi-read fixtures still fan out and synthesize (no companion-primary forced by this phase).
- **SC-003**: 0% of tested conductor-turn fixtures change nested 152 pause/resume behavior.
- **SC-004**: 100% of tested deny/block fixtures keep the completed sibling’s work in the combined reply and do not perform the denied/blocked write.
- **SC-005**: Existing `test_compound_mixed_read_write_still_strictest_wins` (or its successor) MUST NOT still assert a single turn-wide AWAIT that holds the read; replace it with per-subtask assertions.

---

## Assumptions

- Remaining parallel traffic after 155 is mostly all-read and act+act; mixed gather+act on this path is a miss/safety net, not the product path.
- Two sibling AWAIT jobs may both be pending (113 already allows concurrent `request_id`s). The UI may show them one after another; both MUST be independently approvable.
- Budget overage upgrades **that** subtask toward AWAIT_CONFIRMATION (152), not a post-hoc freeze of siblings that already evaluated EXECUTE in the same check.
- Eval may add one parallel mixed-decision id; 154/155 conductor ids stay valid.

## Out of Scope

- Sequential graph execute / feeding prior outputs between fan-out specialists.
- Changing 155 mixed rewrite or 153 sequential rewrite.
- Stall/replan, promote, procedures, swarm.
- Retuning specialist Mode tables (email create may still be DRAFT_ONLY).

## Verbatim Constraints

- `is_compound`
- `request_id`
- `CapabilityGate`
- `GateDecision`
- `EXECUTE`
- `AWAIT_CONFIRMATION`
- `DRAFT`
- `BLOCKED`
- `run_delegate`
- Principle VIII
