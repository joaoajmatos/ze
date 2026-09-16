# Feature Specification: Governed Procedure Activation

**Feature Branch**: `139-procedure-activation`
**Created**: 2026-09-15
**Status**: Implemented
**Input**: User description: "Roadmap Phase 139: make validated procedures discoverable for all relevant agents and planners, with trigger/precondition matching, explicit invocation, action traceability to procedure version, and outcome feedback to review/confidence. Include minimal management/review UX/API, disablement/edit/evidence view. Procedures are advisory and capability-gated; matching must narrow not expand allowed tools. No automatic unreviewed execution, no signal_sources rewiring, no contribution arbitration. Pre-v1 hard cuts allowed."

**Depends on**: Roadmap Phase 138, Governed Procedure Lifecycle. Phase 138 owns the procedure lifecycle, versioning, review decisions, evidence records, and validated/disabled eligibility state. This phase consumes that governed lifecycle; it does not recreate it.

## Overview

Ze already extracts reusable procedures from completed goals and workflows, but stored procedures are only passive planner context. This phase turns a Phase-138-validated procedure into an advisory resource that relevant agents and planners can discover, inspect, and explicitly invoke.

A matching procedure provides its trigger, satisfied and unsatisfied preconditions, steps, and the subset of already-authorized tools relevant to its steps. It never grants a tool, bypasses a capability decision, or silently runs. An explicit invocation records the exact procedure version used for each action and feeds the outcome back to the governed review/confidence lifecycle. Users can minimally inspect, edit, disable, and review evidence for a procedure.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Discover validated procedures for a task (Priority: P1)

When an agent or planner is preparing work, it can retrieve only validated, enabled procedures whose trigger and preconditions are relevant to the current task. The returned guidance identifies why it matched and which prerequisites still need attention.

**Why this priority**: Reliable discovery is the prerequisite for procedure reuse and must never surface unreviewed or disabled guidance as actionable.

**Independent Test**: Seed procedures in each Phase-138 lifecycle state and evaluate a task context. Assert that only validated and enabled versions match, results include trigger/precondition rationale, and irrelevant or unmet-precondition procedures are not presented as ready to invoke.

**Acceptance Scenarios**:

1. **Given** a validated, enabled procedure whose trigger and required preconditions match a planner's task, **When** the planner requests procedure guidance, **Then** it receives the procedure version, matching rationale, steps, and advisory status.
2. **Given** a proposed, under-review, rejected, superseded, or disabled procedure, **When** the same task is evaluated, **Then** it is excluded from actionable matches.
3. **Given** a procedure with a relevant trigger but an unsatisfied required precondition, **When** matching runs, **Then** it is returned only as blocked guidance with the unmet condition, never as ready to invoke.

---

### User Story 2 - Invoke an applicable procedure explicitly and safely (Priority: P1)

An agent or planner may explicitly select a ready procedure while handling an eligible request. Ze presents the procedure as advice, keeps every action subject to the existing capability gate, and limits the available tool set to the intersection of agent-authorized tools, capability-permitted tools, and procedure-relevant tools.

**Why this priority**: Invocation is the value-producing step, but its safety boundary must be stronger than ordinary tool execution.

**Independent Test**: Invoke a validated matching procedure in a mocked agent turn. Assert that no action occurs before explicit selection, the procedure can only narrow the original allowed tools, and denied or unreviewed procedures cannot drive execution.

**Acceptance Scenarios**:

1. **Given** a ready, validated procedure and an agent that explicitly invokes it, **When** it proposes a step action, **Then** the normal capability gate decides whether that action may execute.
2. **Given** a procedure lists a tool the agent or capability gate did not allow, **When** it is invoked, **Then** that tool remains unavailable.
3. **Given** a matching validated procedure, **When** no agent or planner explicitly invokes it, **Then** Ze does not execute any procedure step.
4. **Given** an unreviewed or disabled procedure identifier, **When** an agent attempts invocation, **Then** invocation is rejected before planning or tool execution.

---

### User Story 3 - Trace procedure-guided actions and improve the procedure (Priority: P2)

After an invoked procedure guides work, a user can see which immutable procedure version informed each action, the action outcome, and the source evidence. Ze records structured outcome feedback so a future Phase-138 review can adjust confidence, request review, or disable the procedure under its existing lifecycle rules.

**Why this priority**: Reuse without provenance makes bad procedures difficult to diagnose and improve.

**Independent Test**: Execute a multi-step mocked invocation with one success and one failure. Assert that each action is linked to the exact invoked version, feedback is recorded once with outcomes, and no direct confidence or lifecycle mutation bypasses Phase 138.

**Acceptance Scenarios**:

1. **Given** an invoked procedure version, **When** an action completes or fails, **Then** its trace identifies the procedure id, immutable version, step reference, and outcome.
2. **Given** a completed invocation, **When** feedback is submitted, **Then** it includes execution context, aggregate outcome, and links to the action traces for governed review.
3. **Given** repeated poor outcomes, **When** feedback is evaluated, **Then** only Phase-138 lifecycle rules may change confidence or review status; this phase does not silently promote or demote a procedure.

---

### User Story 4 - Manage and review procedure guidance (Priority: P2)

A user can list procedure guidance, inspect a version with its evidence and use outcomes, edit it through the governed revision flow, and disable it immediately. The interface distinguishes currently usable guidance from history and makes any disabled or pending-review state clear.

**Why this priority**: Users need a small, trustworthy control surface before procedure reuse becomes broadly visible.

**Independent Test**: Create lifecycle fixtures and exercise list, detail/evidence, edit, and disable operations. Assert state labels, immutable historical versions, and immediate exclusion of disabled procedures from matching.

**Acceptance Scenarios**:

1. **Given** procedures at different lifecycle states, **When** the user opens procedure management, **Then** they see name, current version, lifecycle/review status, confidence, trigger, and last-use outcome.
2. **Given** a procedure detail view, **When** the user opens its evidence, **Then** they can see source evidence and activation outcomes without altering them.
3. **Given** a validated procedure, **When** the user edits or disables it, **Then** the Phase-138 revision/disable rules apply and the old version remains traceable.

### Edge Cases

- A procedure may match semantically but lack enough task facts to evaluate a precondition; it is advisory blocked guidance, not executable guidance.
- If a procedure version changes after invocation begins, the active invocation continues to reference its initially selected immutable version; a later action must not drift to the new version.
- If a capability decision changes during an invocation, later actions use the current decision and may be denied even if earlier steps succeeded.
- If trace or feedback persistence fails, Ze must not claim the action was procedure-traceable; it follows the existing action failure/audit policy and surfaces a recoverable failure.
- Procedures whose steps require no tools remain advisory plans; they do not acquire execution privileges.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST use Phase-138 lifecycle eligibility to expose only validated, enabled, current procedure versions as actionable matches.
- **FR-002**: System MUST match procedure triggers and preconditions against an agent/planner task context and return a clear readiness result: ready, blocked with unmet conditions, or not relevant.
- **FR-003**: Matching MUST be available to every relevant agent and planner through a common discovery contract, rather than being limited to goal planning.
- **FR-004**: System MUST present matching procedures as advisory guidance and MUST require an explicit agent/planner invocation before any procedure-guided action is proposed.
- **FR-005**: System MUST reject invocation of a procedure that is not validated, enabled, current, and ready for the supplied context.
- **FR-006**: Every procedure-guided action MUST pass the existing capability gate independently; procedure invocation MUST NOT approve, execute, or confirm an action by itself.
- **FR-007**: The tools available during a procedure-guided action MUST equal an intersection of already-allowed agent tools, current capability-permitted tools, and procedure-relevant tools. Procedure matching or invocation MUST NOT expand permitted tools.
- **FR-008**: System MUST record the immutable procedure id and version, invocation id, and procedure step reference on every procedure-guided action trace.
- **FR-009**: System MUST record a structured invocation outcome and action references as feedback to the Phase-138 governed review/confidence lifecycle. This phase MUST NOT directly mutate lifecycle state or confidence outside that lifecycle.
- **FR-010**: System MUST provide minimal management operations to list procedures, view a procedure version and its evidence/outcomes, submit a governed edit, and disable a procedure.
- **FR-011**: Editing MUST create or use the Phase-138 governed revision path; historical versions and their activation traces MUST remain readable.
- **FR-012**: Disabling MUST immediately make a procedure ineligible for new matches and invocations while preserving existing evidence and traces.
- **FR-013**: REST responses and user interface state MUST distinguish validated/ready guidance from pending review, blocked, superseded, rejected, and disabled records.
- **FR-014**: System MUST preserve current planner procedure retrieval as a hard-cut migration to the common discovery contract; no parallel ungated procedure retrieval path may remain after this phase.
- **FR-015**: This phase MUST NOT automatically execute an unreviewed procedure, rewire `signal_sources()`, add contribution arbitration, or change contribution collision behavior.

### Key Entities

- **Procedure version**: The immutable, Phase-138-governed revision containing trigger, preconditions, steps, allowed-tool narrowing hints, evidence, lifecycle status, and confidence.
- **Procedure match**: An ephemeral assessment of one procedure version against a task context, including relevance, readiness, and precondition rationale.
- **Procedure invocation**: A durable record that an agent or planner explicitly selected one immutable procedure version for a task.
- **Procedure action trace**: The existing action trace enriched with invocation, procedure version, and step identifiers.
- **Procedure outcome feedback**: A durable summary of invocation/action results submitted to the governed review/confidence lifecycle.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In automated tests, 100% of actionable procedure matches are validated and enabled; unreviewed, disabled, and superseded versions produce zero actionable matches.
- **SC-002**: In automated tests, 100% of procedure-guided tool sets are subsets of the corresponding non-procedure agent/capability tool set.
- **SC-003**: In automated tests, 100% of procedure-guided actions carry an immutable procedure version and step reference that resolves from the trace.
- **SC-004**: A user can list, inspect evidence for, edit through review, and disable a procedure in one management session without losing historical traces.
- **SC-005**: All relevant planner and agent discovery integrations use the common contract, verified by dedicated integration tests and a repository scan for retired direct retrieval paths.

## Assumptions

- Phase 138 supplies durable lifecycle states, immutable version semantics, review/evidence records, confidence ownership, and the governed edit/disable transition rules.
- “Relevant agents and planners” means registered agents/planners that already receive task context and can use advisory context; agents without an execution/planning context need no integration.
- Explicit invocation may be an agent/planner decision recorded in the turn or planning trace; it is not a new end-user confirmation category and does not replace existing capability confirmations.
- Existing trace storage can be extended or a Phase-138-owned activation record can reference it; the implementation plan chooses the smallest durable shape.

## Out of Scope

- Defining, reviewing, approving, versioning, or confidence-scoring the procedure lifecycle itself (Phase 138).
- Autonomous execution, background procedure runs, or automatic execution of any unreviewed procedure.
- A general workflow engine rewrite or converting procedure steps into executable workflows.
- New `signal_sources()` wiring, contribution submission changes, collision detection changes, or contribution arbitration.
- Multi-user permissions, sharing, marketplace distribution, or compatibility shims for pre-v1 APIs.
