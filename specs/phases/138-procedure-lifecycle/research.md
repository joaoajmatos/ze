# Research: Governed Procedure Lifecycle

## R1. Procedure is guidance, not a plan or record

**Decision:** Define a Procedure as a reusable operational playbook with a trigger,
preconditions, ordered steps, success criteria, and limits. Keep Goal/Workflow plans as
intent-specific execution definitions and ActionRecord as an observation of one execution.

**Rationale:** Reusing a plan would conflate future guidance with a particular objective or
schedule. Reusing an action record would turn a single outcome into policy.

**Alternatives considered:** Store only rendered text from goals/workflows — rejected because it
cannot carry review, version lineage, or evidence. Treat skills as procedures — rejected because
skills include tool-authority concerns that this phase must not broaden.

## R2. One admission service is the write boundary

**Decision:** All sources construct a `ProcedureCandidate` and submit it to one admission
service. That service alone writes candidates, decisions, active versions, supersession, and
feedback links.

**Rationale:** It makes the trust boundary observable and lets source-specific evidence be judged
consistently. It also satisfies the hard cut rather than concealing old writers behind a wrapper.

**Alternatives considered:** Put checks inside `propose_procedure` while preserving call sites —
rejected as an ungated public door under a new implementation. Allow dream promotion to insert
after its own review — rejected as a second writer.

## R3. Reuse Phase 137 evidence and learning

**Decision:** Candidate support, review rationale, version change rationale, rollback rationale,
and use feedback reference Phase 137 Evidence and Learning by id/value contract. Procedure
types add no duplicate `source_type`, evidence scoring model, or learning table.

**Rationale:** Evidence must retain its origin and learning context across all sources. A
procedure-local vocabulary would sever those semantics and cause divergent retention rules.

**Alternatives considered:** `source_refs: list[UUID]` alone — rejected: it cannot state what
the reference establishes or whether it is supporting, countervailing, or reviewer evidence.

## R4. Source trust is explicit, admission is not automatic

**Decision:** Completed goals/workflows, approved workspace runs, repeated action patterns,
explicit instruction, reviewed dream/reflection proposals, and imported skills all create
candidates. Source class determines initial provenance and review posture; none bypasses
admission. Only approved workspace runs are eligible.

**Rationale:** Completion is evidence of execution, not proof of reuse. A reviewed reflection
artifact is still synthesized. User instruction is prompt-supplied but may lack sufficient
operational detail.

**Alternatives considered:** Auto-admit user instructions or successful runs — rejected because
each may be narrow, stale, unsafe, or incomplete.

## R5. Version lineage, not in-place mutation

**Decision:** A canonical Procedure identity has immutable content versions. One active version
may exist at a time. Admitting a material replacement supersedes the previous version; rollback
records its cause and restores only an eligible prior version or retires the identity.

**Rationale:** Operators need to trace which advice was used and why it changed. In-place edits
would corrupt feedback attribution.

**Alternatives considered:** Update the active row in place — rejected. Keep several active
variants — rejected because retrieval would select between competing methods without an
arbitration design.

## R6. Feedback describes use; it does not rewrite

**Decision:** `ProcedureFeedback` is append-only and links a ProcedureVersion to a pre-existing
ActionRecord/equivalent execution result. Feedback may open review, affect confidence, support a
new candidate, or justify rollback. It cannot automatically alter steps.

**Rationale:** Outcome data is evidence, but translating it into a new method is a deliberative
admission decision.

**Alternatives considered:** Automatically patch steps after a failed run — rejected as
unreviewed policy mutation.

## R7. Provisional procedures require terminal resolution

**Decision:** Replace the executor's process-local provisional-procedure map with a durable
provisional/candidate handoff, or intentionally discard it at every terminal path. Completion
submits it to admission; abandonment, cancellation, and restart recovery discard it with a
reason unless independently reconstituted as a candidate.

**Rationale:** Process-local data disappears on restart and has no audit state. A candidate must
not be accidentally reused before it is admitted.

**Alternatives considered:** Persist local provisional procedures as active immediately — rejected
because it bypasses review. Keep the in-memory map as a fallback — rejected as ambiguous
durability.

## R8. Hard-cut migration posture

**Decision:** Remove `MemoryStore.propose_procedure` from public contracts and eliminate dream
direct `memory_procedures` INSERT. Migrate legacy rows once into a clearly labeled legacy
candidate/version state or retire them according to a documented decision; no dual read/write.

**Rationale:** The old table has no evidence, admission, or version semantics. Pre-v1 permits a
clear semantic break.

**Alternatives considered:** Retain legacy writer as a deprecated alias — rejected by the
explicit no-shim constraint.
