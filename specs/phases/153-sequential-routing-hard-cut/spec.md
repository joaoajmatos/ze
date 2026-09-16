# Feature Specification: Sequential Routing Hard-Cut

**Feature Branch**: `153-sequential-routing-hard-cut`

**Created**: 2026-09-16

**Status**: Implemented

**Input**: User description: "153 Sequential routing hard-cut: Sequential/mixed/dependent → companion as primary. Update companion description + conductor instructions. Independent multi-read stays fan-out+synthesize. Single-domain stays specialist. DELETE `plan_sequential`, sequential edge to END, unused `dynamic_plan_steps`. Haiku `is_sequential` means conductor. Turn-local progress ledger + MessageTrace. Scale effort. No durable promote."

**Governed by**: [`specs/arch/companion-conductor-roadmap.md`](../../arch/companion-conductor-roadmap.md) phase 153, [`specs/arch/pre-v1-hard-cuts.md`](../../arch/pre-v1-hard-cuts.md) (no wrap-then-replace), [`specs/arch/ze-doctrine.md`](../../arch/ze-doctrine.md), [`151-fat-delegate-aci`](../151-fat-delegate-aci/spec.md), [`152-per-delegate-gate`](../152-per-delegate-gate/spec.md), [`142-speech-act-routing`](../142-speech-act-routing/spec.md). Plugin isolation: companion MUST NOT import calendar or messenger tools; it delegates.

**Depends on**: 151 fat isolated workers; 152 per-delegate gates/confirmations (otherwise companion-primary mixed turns would inherit EXECUTE).

**Does not start**: 154 observability/eval product UI (this phase may record a ledger onto `MessageTrace` for 154 to show). Durable promote to workflow/goal is after 154.

---

## Overview

Sequential compound today calls a workflow planner and then **ends**. Independent parallel compound still fans out and synthesizes. Users who need “check Tuesday then email them the slot” do not get an in-chat conductor.

This phase is the product change: sequential, mixed, and dependent turns route to **companion as primary**. Companion’s embedding `description` and instructions finally match that job. Independent multi-read stays graph fan-out plus synthesize. Single-domain stays the specialist. `plan_sequential`, the sequential edge to END, and `dynamic_plan_steps` are **deleted** in this phase — not wrapped. Haiku `is_sequential` means “use the conductor,” not “run a workflow planner.” Companion plans briefly, briefs specialists with 151, judges done/next/ask-user, and scales effort (no four specialists for “what’s on Tuesday”). Progress is a turn-local ledger recorded on the message trace. Work that must outlive the turn is still not auto-promoted.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Dependent work is one conversation with Ze (Priority: P1)

The user asks something that needs calendar then email (the second step needs the first’s output). The router sends companion as the primary speaker. Companion checks the calendar via delegate, then briefs messenger with the event id in `prior_outputs` / `inputs`. The user hears one voice. Specialists do not take the mic. The old planner→END path is gone.

**Why this priority**: First user-visible collaboration; killing `plan_sequential` later would leave two sequence owners.

**Independent Test**: Sequential/dependent envelope → primary agent companion, `execute_tool` runs companion, not `plan_sequential`. No `plan_sequential` node. Graph tests for `after_decompose == plan_sequential` are deleted, not aliased.

**Acceptance Scenarios**:

1. **Given** Haiku/decompose marks the turn sequential or dependent, **When** the graph continues, **Then** companion is `primary_agent` / the executed agent, and `plan_sequential` is not called.
2. **Given** that turn, **When** companion works, **Then** it may `delegate_to_agent` (151) with fat briefs; the user-facing reply is companion’s.
3. **Given** this phase ships, **When** code is searched, **Then** `plan_sequential`, `dynamic_plan_steps`, and `dynamic_plan_high_risk` are gone from conversation graph, state, and turn plumbing (workflow agent planner for real workflows may remain).
4. **Given** `_execute_compound` sequential loop, **When** this phase ships, **Then** it is deleted; sequential work MUST NOT execute as a graph list of specialists.

---

### User Story 2 - Independent reads still fan out; single-domain still specialist (Priority: P1)

Two independent lookups (news and calendar, neither needs the other) still run in parallel and synthesize. “What’s on Tuesday?” still goes to calendar, not companion spawning extras. Speech-act one-shots still companion→one delegate (142/146).

**Why this priority**: Conductor is for dependence, not a swarm for every compound.

**Independent Test**: Compound + not sequential → still `asyncio.gather` + synthesize. Single-agent envelope → that specialist. Calendar-only prompt does not execute companion as primary.

**Acceptance Scenarios**:

1. **Given** independent multi-read (`is_compound` and not `is_sequential`), **When** the graph runs, **Then** fan-out + synthesize still occurs and companion is not forced primary.
2. **Given** a single-domain calendar (or email, research) turn, **When** routed, **Then** that specialist remains primary.
3. **Given** “what’s on Tuesday?”, **When** companion is not primary, **Then** calendar handles it; conductor instructions still say not to spawn four specialists if it ever did see that prompt.
4. **Given** speech-act remind/cancel, **When** companion is primary as today, **Then** one-shot delegates still work (151/146).

---

### User Story 3 - Embeddings and instructions agree; effort scales; ledger is turn-local (Priority: P2)

Companion `description` includes coordinating calendar and email in chat (so embeddings stop sending mixed turns away). Instructions: short plan, fat briefs, judge done/next/ask-user, throw away the Haiku hint if the specialist result changes the job. A turn-local ledger records which specialist ran; it is written onto `MessageTrace`. No promote-to-workflow.

**Why this priority**: 151 forbade description changes; this phase is when they must change.

**Independent Test**: Companion `description` differs from 151 lock and mentions coordination. State has a turn-local ledger copied to trace. No new workflow row created for an in-chat sequence.

**Acceptance Scenarios**:

1. **Given** companion `description` after this phase, **When** embeddings are rebuilt from it, **Then** mixed calendar/email coordination is in-scope for companion (not “not for calendar, email…”).
2. **Given** a conductor turn, **When** it finishes, **Then** `MessageTrace` includes the turn-local ledger (plan/hint + specialists attempted) even if the web panel is still 154.
3. **Given** a job that would take weeks, **When** this phase ships, **Then** Ze does not auto-create a workflow or goal from the conductor (ask or stop; promote is later).
4. **Given** Haiku lists four steps for a simple calendar read that was wrongly marked sequential, **When** companion conducts, **Then** instructions require scaling down (one specialist or none extra).

---

## Edge Cases

- Haiku `is_sequential` true on a simple single-domain prompt: companion still scales down; may immediately delegate once or the rewrite should not happen if decompose also says a single agent — **Assumption**: sequential flag with one subtask is not conductor; treat as that specialist.
- Sequential flag with one subtask: stay specialist (no companion steal).
- `is_sequential` false, two dependent agents: Haiku bug; 154 eval should catch; do not add a second classifier this phase unless decompose already has a dependency bit.
- Confirmation mid-sequence: 152 pause/resume; 153 must not reset envelope to `plan_sequential` on resume.
- Plugin isolation: companion still has only remember/forget/delegate tools.
- Workflow **agent** (user asked for a durable workflow) is unchanged; only conversation-graph `plan_sequential` dies.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: When decompose/Haiku marks a turn sequential/mixed/dependent with **more than one** specialist, the system MUST set companion as the primary executed agent with the user’s original prompt. Haiku subtasks MAY be a non-executable hint only.
- **FR-002**: Independent compound (`is_compound` and not sequential) MUST keep graph fan-out + synthesize. Single-domain MUST keep the specialist primary.
- **FR-003**: System MUST delete conversation-graph `plan_sequential`, the `after_decompose` edge to that node and to END, `dynamic_plan_steps`, `dynamic_plan_high_risk`, and the sequential branch of `_execute_compound`. No shim node that still plans then END. Workflow **domain** planner for stored workflows MAY remain.
- **FR-004**: `is_sequential` MUST mean “conductor” (companion primary) for routing, not “workflow planner.”
- **FR-005**: Companion class `description` MUST be updated so embeddings include in-chat calendar/email/reminder coordination via specialists. Instructions MUST describe the inner loop: short plan, fat 151 briefs, judge done/next/ask-user, scale effort, discard the hint after a specialist returns if needed.
- **FR-006**: System MUST keep a turn-local progress ledger on graph/agent state and record it on `MessageTrace`. It MUST NOT persist a durable workflow/goal from that ledger.
- **FR-007**: Companion MUST NOT import calendar or messenger tools. Research MUST NOT regain `delegate_to_agent`. Specialists MUST NOT speak as the user-facing agent on conductor turns. Nested invocations MUST keep 152 per-delegate gates and 113 `request_id` confirmations.
- **FR-008**: This phase MUST NOT implement promote-to-workflow/goal, stall outer loop as a new Magentic product, 154 trace **panel** / eval YAML (beyond storing ledger fields), or per-subtask parallel graph gates.

### Key Entities

- **Conductor turn**: Sequential/mixed/dependent, multi-specialist, companion primary.
- **Haiku hint**: Decompose subtasks stored as non-executable context.
- **Turn-local ledger**: In-memory list of specialist invocations this turn (name, status, optional confirmation id); copied to `MessageTrace`.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of tested multi-specialist sequential fixtures execute companion and 0% call `plan_sequential`.
- **SC-002**: 100% of tested independent parallel fixtures still synthesize from multiple `subtask_results` without companion primary.
- **SC-003**: 100% of tested single-domain fixtures keep the specialist primary.
- **SC-004**: Repo search after the phase finds 0 conversation-graph references to `plan_sequential` or `dynamic_plan_steps`.
- **SC-005**: 100% of tested conductor turns write a ledger onto `MessageTrace`; 0 auto-created workflows from those turns.

---

## Assumptions

- “More than one specialist” is the bar for conductor rewrite; one sequential subtask stays that agent.
- Independent vs dependent is the existing Haiku `sequential` / `is_sequential` bit; no new model this phase.
- 151 and 152 are Implemented before this product code. Conductor turns still evaluate **each** `run_delegate` (152); companion-primary MUST NOT restore wholesale parent `gate_decision` inherit.
- Progress **keys** and eval YAML files are 154; 153 only needs a ledger structure on state/trace.

## Out of Scope

- 154 panel, progress locale copy, eval scenarios (specify them next; do not implement here).
- Promote to workflow/goal.
- Feeding prior outputs inside `_execute_compound` sequential (deleted).
- Swarm / specialist-as-speaker.

## Verbatim Constraints

- `plan_sequential` (deleted)
- `dynamic_plan_steps` (deleted)
- `dynamic_plan_high_risk` (deleted)
- `is_sequential`
- `delegate_to_agent`
- `MessageTrace`
- companion `description` (updated this phase)
- Principle VIII

## After this feature / Future work

154 observability and eval. Then stall/replan loop and promote-to-workflow.
