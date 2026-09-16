# Research: Governed Procedure Activation

## R1. Lifecycle authority

**Decision:** Phase 139 consumes Phase 138's `ProcedureIdentity`, `ProcedureCandidate`, `ProcedureAdmission`, immutable `ProcedureVersion`, `ProcedureFeedback`, and lifecycle-event contracts. This phase adds the requested disablement control through the governing retirement/disable transition rather than duplicating state transitions or calculating confidence itself.

**Rationale:** Activation is a consumer of governance. A second lifecycle would let an activation path promote unreviewed guidance or make feedback disagree with review history.

**Alternatives considered:** Add `approved`/`disabled` booleans to the current `Procedure` dataclass — rejected because this recreates Phase 138 and loses versioned evidence.

## R2. Shared deterministic match contract

**Decision:** Define a common `ProcedureDiscovery` contract that accepts normalized task context and returns `ProcedureMatch` records with relevance, precondition evaluation, and readiness. Use retrieval to bound candidates, then deterministic trigger/precondition checks; do not make a new LLM call just to select a procedure.

**Rationale:** Every context-bearing agent/planner needs the same safety semantics. Candidate retrieval alone is not eligibility; it can return semantically adjacent procedures with unmet prerequisites.

**Alternatives considered:** Let each planner format and filter `MemoryContext.procedures` itself — rejected because it preserves the present goal-only, inconsistent path. LLM-only matching — rejected because it is less auditable and may treat an unmet precondition as satisfied.

## R3. Match states

**Decision:** A match reports `not_relevant`, `blocked`, or `ready`. Only a validated, enabled, current version with all required preconditions satisfied can be `ready`. Unreviewed, rejected, superseded, and disabled versions are excluded before matching.

**Rationale:** This separates “useful to mention” from “eligible to invoke” and makes a missing fact explicit rather than turning uncertainty into permission.

**Alternatives considered:** Return all semantically similar procedures with a score — rejected because consumers could mistake review-ineligible content for ready guidance.

## R4. Explicit invocation and tool narrowing

**Decision:** Introduce an explicit invocation record before a procedure-guided step is planned. For each step, compute `effective_tools = agent_allowed ∩ capability_allowed ∩ procedure_relevant`. An empty intersection is a blocked step, not a fallback to broader tools.

**Rationale:** Procedures advise how work can be done; they cannot be an alternate capability system. Intersection is monotonic: a procedure never expands authority.

**Alternatives considered:** Treat a match as invocation — rejected because discovery must not cause action. Treat procedure tool hints as a tool grant — rejected by the feature constraints and existing capability model.

## R5. Immutable action provenance

**Decision:** Persist an invocation id and selected `procedure_id` plus immutable `procedure_version`; link each action trace to invocation and stable step reference/index. Store the version snapshot or revision foreign key required by Phase 138 so historical traces resolve even after edits or disablement.

**Rationale:** Name-only provenance becomes ambiguous after revision. A version identifier makes an action explainable and preserves evidence for review.

**Alternatives considered:** Record procedure name only on `MessageTrace` — rejected because names can be edited/reused and traces could not establish which guidance was followed.

## R6. Outcome feedback

**Decision:** Complete/cancel/fail invocation paths produce one idempotent aggregate feedback record referencing the action traces. Feedback is submitted to Phase 138's review/confidence intake; Phase 138 decides whether it changes confidence, requests review, or disables the version.

**Rationale:** A failed action is evidence, not automatically proof that the procedure is wrong. Idempotency prevents retries or streaming events from double-counting outcomes.

**Alternatives considered:** Directly decrement confidence after failure — rejected as a bypass of Phase 138 governance. Free-text-only logs — rejected because review needs structured trace links and outcome classification.

## R7. Minimal management surface

**Decision:** Expose list, detail/version, evidence/outcomes, governed edit, and disable endpoints. Add one procedure management widget/page using entity query hooks and review mutations; it shows status/confidence/readiness but does not offer direct approval outside Phase 138.

**Rationale:** The user needs visibility and a fast safety stop. Keeping approval in Phase 138 prevents the activation UI from becoming a conflicting lifecycle console.

**Alternatives considered:** Chat-only management tools — rejected because browsing evidence and history needs a durable readable view. Full workflow editor — rejected as out of scope.

## R8. Migration and cut

**Decision:** Replace goal planner direct procedure retrieval with `ProcedureDiscovery`, then integrate the same contract at every registered agent/planner that has task context. Remove the old direct retrieval surface from production callers in this phase; tests adapt to the shared contract.

**Rationale:** Pre-v1 hard cuts avoid a permanently divergent goal-only path.

**Alternatives considered:** Keep old retrieval as a compatibility fallback — rejected by Constitution Principle VIII and FR-014.

## Delivered Phase-138 APIs (T001)

Eligible versions: `ProcedureAdmissionService.retrieve_procedures()` and `ProcedureStore.list_active_versions()` (identity `ACTIVE` and version `ACTIVE`).

Revision: `submit_procedure_candidate` with `proposed_identity_id`, then `review_procedure_candidate(APPROVE)` — also used by REST `POST /procedures/{id}/edit`.

Evidence: `ProcedureVersion.evidence_refs` and `lifecycle_history()`.

Confidence/review intake: `record_procedure_feedback` (ActionRecord-backed) and `ingest_activation_feedback` (invocation-backed). Neither mutates version confidence in Phase 139.

Disable: `disable_procedure` retires the identity and the active version.

## Agent/planner integrations (T002)

| Consumer | Path | Test |
|---|---|---|
| All graph agents | `fetch_context` → `attach_procedure_matches` | `test_procedure_discovery.py` |
| Goal planner | `GoalPlanner._fetch_procedures` → `ProcedureDiscovery.match` | `test_planner.py` |
| Workflow planner | `WorkflowPlanner._fetch_procedures` → `ProcedureDiscovery.match` | `test_workflow_planner.py` |

No plugin agent imports procedure internals. Direct `memory.retrieve` procedure fallback is removed.

