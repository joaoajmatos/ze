# Feature Specification: Governed Procedure Lifecycle

**Feature Branch**: `138-procedure-lifecycle`  
**Created**: 2026-09-15  
**Status**: Implemented  
**Input**: User description: "Create Phase 138: a governed lifecycle for reusable operational procedures. Depend on Phase 137 evidence/learning vocabulary. Replace all procedure writers with one admission path; hard-cut direct `MemoryStore.propose_procedure` and dream direct INSERT, no shim. Include candidates, evidence/provenance, admission review, version/supersession/rollback/failure feedback, and resolve process-local provisional procedures with persistence or intentional removal. Sources include completed goals/workflows, approved workspace runs, repeated action patterns, explicit user instruction, reviewed dream/reflection proposals, and imported skills. Do not broaden skills execution or add generic arbitration."

**Governed by**: `specs/arch/contribution-seam.md` (a proposal is not a write; no generic arbitration), `specs/arch/claim-topology.md` (shared provenance and confidence), and `specs/arch/pre-v1-hard-cuts.md` (remove obsolete public writers rather than shimming them). **Depends on Phase 137** for its canonical evidence and learning vocabulary; this phase consumes those types and their source-reference rules without redefining them.

## Overview

Ze currently calls several unrelated things a procedure: a goal or workflow extractor writes
directly to memory, a dream promoter inserts directly into the procedure table, and a goal
executor keeps provisional procedures only in its process. Those paths have materially
different trust levels, no common review record, and no way to tell whether a later failure
invalidated the advice.

A Procedure in this phase is a reusable operational playbook: a stable description of when to
act, prerequisites, ordered method, verification, and known limits. It is not a goal's
objective, a workflow definition, a scheduled plan, or an ActionRecord of what happened once.
It may guide future work but does not itself execute skills, tools, or workspace commands.

This phase creates one governed admission lifecycle. Every source first produces a candidate
with Phase 137 evidence and honest provenance. Admission either approves a versioned playbook,
rejects it with a reason, or holds it for review. Later evidence can supersede a version,
roll it back, or record failure feedback. The existing direct writers are hard-cut: no public
`MemoryStore.propose_procedure`, no dream-table INSERT shortcut, and no compatibility alias.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Ze promotes only grounded reusable playbooks (Priority: P1)

After a completed goal or workflow, an approved workspace run, a repeated action pattern, an
explicit user instruction, a reviewed reflection proposal, or an imported skill suggests a
method worth keeping, Ze creates a ProcedureCandidate rather than silently storing a procedure.
The candidate shows its source evidence, provenance, intended trigger, and proposed steps.

**Independent Test**: Submit one candidate from every supported source. Assert all reach the
same admission entry point, retain Phase 137 evidence references and provenance, and none write
directly to the procedure store.

**Acceptance Scenarios**:
1. **Given** a completed goal or workflow with reusable learning, **When** extraction proposes a
   playbook, **Then** it is a candidate with links to the completed record and its learning
   evidence, not the goal/workflow plan itself.
2. **Given** a workspace run that is not approved, **When** it resembles a useful method,
   **Then** it cannot become an admitted procedure.
3. **Given** an imported skill, **When** it contributes a reusable instruction, **Then** the
   resulting candidate records the skill as source evidence and does not expand that skill's
   permissions or execution behavior.
4. **Given** a reviewed dream/reflection proposal, **When** it is considered, **Then** it enters
   the same admission path with synthesized provenance and reviewer evidence.

### User Story 2 — The user can trust an admitted procedure's review state (Priority: P1)

Ze admits a candidate only after applying reusable-playbook checks: sufficient attributable
evidence, a meaningful trigger, bounded prerequisites and steps, verifiable success criteria,
and no conflict with an active canonical procedure for the same operational purpose. Admission
records a decision and reason. A human-required source or a low-confidence proposal remains
reviewable rather than becoming active by implication.

**Independent Test**: Exercise approval, rejection, and needs-review outcomes. Assert an
approved candidate produces exactly one active procedure version; rejected and pending
candidates are not retrievable as playbooks.

**Acceptance Scenarios**:
1. **Given** an explicit user instruction that is complete and safely reusable, **When** it is
   submitted, **Then** the reviewer may admit it with prompt-supplied provenance and the user
   instruction as evidence.
2. **Given** a candidate missing required evidence or a success check, **When** reviewed, **Then**
   it is rejected or held with a durable reason and creates no active procedure.
3. **Given** two candidates for the same procedure identity, **When** one is admitted, **Then**
   the system has one canonical active version rather than two silently competing playbooks.

### User Story 3 — Procedures improve without erasing history (Priority: P1)

When stronger evidence or user revision changes an admitted playbook, Ze creates a new version
and marks the former active version superseded. If the new version proves harmful or wrong, it
can be rolled back to the last suitable version with the decision and evidence preserved.

**Independent Test**: Admit v1, admit a revised v2, then roll back v2. Assert the version chain,
active version, supersession reason, and rollback evidence are all preserved.

**Acceptance Scenarios**:
1. **Given** an active procedure and a materially improved candidate for the same identity,
   **When** admitted, **Then** the candidate becomes the next version and v1 becomes superseded.
2. **Given** a superseded procedure, **When** history is viewed, **Then** its content, evidence,
   admission decision, and successor remain available for audit.
3. **Given** failure feedback that invalidates the current version, **When** rollback is approved,
   **Then** the current version is rolled back and a prior eligible version is restored or the
   procedure is retired when none is safe.

### User Story 4 — Runtime results feed back into procedure quality (Priority: P2)

When a procedure is used as guidance, Ze records an ActionRecord-style outcome as feedback
against that version. It does not confuse the recorded action with the reusable playbook.
Repeated failures lower confidence or trigger review; successes provide evidence but do not
silently rewrite steps.

**Independent Test**: Associate successful and failed action records with an active procedure.
Assert feedback is append-only, preserves the execution record identity, and a failure can
create a review request without changing the procedure's content automatically.

### User Story 5 — Provisional goal procedures cannot vanish ambiguously (Priority: P2)

Goal-local provisional procedures must have an explicit terminal outcome. On goal completion,
each is submitted as a candidate and either persisted through admission or rejected/withdrawn
with a recorded reason. On abandonment, restart, or cancellation, it is intentionally removed
or recorded as discarded; it is never treated as an invisible durable memory.

**Independent Test**: Complete, abandon, and restart a goal holding a provisional procedure.
Assert completion submits it to admission; all non-completion paths remove it intentionally and
no process-local item is retrieved after its owning execution ends.

## Edge Cases

- A repeated action pattern is evidence for a candidate, not automatic proof of a good
  procedure; failures and unapproved runs count as counter-evidence.
- A procedure imported from a skill remains a playbook reference. This phase must not cause a
  skill to run, widen `allowed-tools`, or bypass the workspace gate.
- A goal/workflow plan may be source evidence but must never be reclassified as its procedure.
- A reviewed dream/reflection proposal may be admitted only with its review decision and source
  evidence; reflection is not granted a direct procedure writer.
- If a source record is deleted or unavailable, its candidate/version stays historically
  attributable and is flagged as unavailable evidence; it is not silently relabeled.
- If no rollback target is eligible, rollback retires the active procedure rather than
  reactivating an unreviewed version.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST define Procedure as a reusable operational playbook distinct from
  Goal, Workflow, their plans, and ActionRecord.
- **FR-002**: Every proposed procedure MUST enter one governed admission path as a
  ProcedureCandidate before an active procedure can persist.
- **FR-003**: Candidates MUST support completed goals, completed workflows, approved workspace
  runs, repeated action patterns, explicit user instructions, reviewed dream/reflection
  proposals, and imported skills as sources.
- **FR-004**: Each candidate, admission decision, version, rollback, and feedback record MUST
  carry Phase 137 evidence references and honest provenance; this phase MUST NOT invent a
  competing evidence or learning vocabulary.
- **FR-005**: Admission MUST decide approve, reject, or needs-review with a durable reason.
  Only an approved candidate may create an active retrievable procedure.
- **FR-006**: Admission MUST validate operational completeness: a trigger, bounded
  prerequisites, ordered steps, success criteria, and evidence sufficient for the source's
  trust posture.
- **FR-007**: The system MUST assign one canonical procedure identity and at most one active
  version per identity. Material revision MUST create a new version and explicitly supersede
  the prior active version.
- **FR-008**: The system MUST support rollback based on attributable feedback or review. It MUST
  preserve the rolled-back version and reason, restore only an eligible prior version, or
  retire the procedure if no eligible version exists.
- **FR-009**: Procedure-use results MUST be recorded as feedback linked to the procedure version
  and an existing ActionRecord/equivalent execution record. Feedback MUST NOT automatically
  rewrite playbook content.
- **FR-010**: Process-local provisional procedures owned by goal execution MUST resolve to an
  admission candidate on successful completion or be intentionally removed/recorded as
  discarded on every other terminal path, including restart recovery.
- **FR-011**: All direct writers MUST be replaced by the admission path: goal completion,
  workflow completion, dream/reflection promotion, and any newly added source in FR-003.
- **FR-012**: `MemoryStore.propose_procedure` MUST be removed from the public contract in this
  phase. Dream promotion MUST NOT directly INSERT into `memory_procedures`. No shim,
  deprecated alias, dual-write, or direct-writer fallback is permitted.
- **FR-013**: Retrieval MUST return only active admitted procedure versions by default and expose
  history only to the appropriate review/audit surface.
- **FR-014**: This phase MUST NOT broaden skill execution, tool access, workspace permissions,
  generic contribution arbitration, or generic action-result production.

### Key Entities

- **Procedure**: An admitted, versioned reusable operational playbook.
- **ProcedureCandidate**: A proposed playbook awaiting an admission decision.
- **ProcedureEvidence / ProcedureLearning**: References using Phase 137's canonical vocabulary.
- **ProcedureAdmission**: The durable review decision and rationale for a candidate.
- **ProcedureVersion**: Immutable procedure content with lifecycle status and lineage.
- **ProcedureFeedback**: Append-only use outcome tied to a version and an ActionRecord.
- **ProvisionalProcedure**: Goal-execution-local candidate material requiring a terminal outcome.

## Success Criteria *(mandatory)*

- **SC-001**: Dedicated source tests show 100% of the seven supported source classes submit
  through the single admission path; zero source test writes directly to a procedure store.
- **SC-002**: 100% of admitted procedures in lifecycle tests have provenance and at least one
  valid Phase 137 evidence reference.
- **SC-003**: Versioning tests maintain exactly one active version per procedure identity across
  admission, supersession, and rollback.
- **SC-004**: Feedback tests show 100% of failed uses remain traceable to both their procedure
  version and underlying ActionRecord without automatic content mutation.
- **SC-005**: Terminal-path tests leave zero unresolved process-local provisional procedures.
- **SC-006**: A production-code scan finds zero public `propose_procedure` calls and zero dream
  direct inserts into the procedure table after the hard cut.

## Assumptions

- Phase 137 has defined evidence and learning value types, source references, and retention
  semantics before implementation begins. If its public names differ, this phase adopts them
  without copying their model.
- “Approved workspace run” means a run whose existing gate/review policy recorded approval; a
  successful but unapproved run is insufficient.
- “Repeated action pattern” is derived evidence from existing execution records and needs
  admission; it is not a new generic arbitration mechanism.
- Existing procedure rows are pre-v1 data. Migration may normalize them into an explicit
  reviewed/imported state or retire them; implementation must choose one documented hard cut,
  never dual-read old and new semantics.

## Out of Scope

- Executing imported skills or changing skill review, `allowed-tools`, or workspace gates.
- Redesigning goals, workflow definitions, schedules, or ActionRecord storage.
- Generic cross-function contribution arbitration or a generic action-result producer.
- Automatic rewriting of a procedure from outcome feedback.
- A general procedure authoring UI beyond the review and audit capability necessary for this
  lifecycle.
