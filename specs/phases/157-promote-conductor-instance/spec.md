# Feature Specification: Promote Conductor Instance to Workflow/Goal

**Feature Branch**: `157-promote-conductor-instance`

**Created**: 2026-09-16

**Status**: Implemented

**Input**: User description: "157 Promote this instance to workflow/goal: When the job must outlive the turn (turn end, abort, confirmation that never returns, user says keep going on this, clearly multi-session). Companion/conductor offers or creates a workflow or goal instance — not a procedure, not memory_procedures, not procedure activation (135–139). Goals/workflows are not the in-chat conductor (pin holds). No swarm."

**Governed by**: [`specs/arch/companion-conductor-roadmap.md`](../../arch/companion-conductor-roadmap.md) phase 157, [`specs/arch/pre-v1-hard-cuts.md`](../../arch/pre-v1-hard-cuts.md), [`specs/arch/ze-doctrine.md`](../../arch/ze-doctrine.md), stall loop [`156-conductor-stall-replan`](../156-conductor-stall-replan/spec.md), mixed routing [`155-mixed-gather-act-conductor`](../155-mixed-gather-act-conductor/spec.md), speech-act goals [`142-speech-act-routing`](../142-speech-act-routing/spec.md), goals [`028-goal-engine`](../028-goal-engine/spec.md), workflows [`012-workflow`](../012-workflow/spec.md). Companion MUST NOT import goal/workflow tools; it delegates (151/152). Procedures 135–139 are out of scope.

**Depends on**: 155/156 so mixed and stalled conductor turns exist to promote. Existing `create_goal` / `create_workflow` on specialist agents. 152 confirmation on those intents.

**Does not start**: Procedure ledger/activation; swarm; making goals/workflows the in-chat sequencer; parallel per-subtask gates.

---

## Overview

The in-chat conductor is turn-local. Some jobs cannot finish in one turn: the graph ends with work left, the user walks away from a confirmation, the run aborts, the user says “keep going on this,” or the work is clearly multi-session. Today Ze either drops that instance or pretends the chat conductor is durable.

This phase lets companion **offer or create a workflow or goal instance** that continues the **same job** — a stored automation instance, not a procedure and not `memory_procedures`. In-chat sequencing stays companion. Specialists still do not take the mic. No swarm.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Unfinished conductor work is offered as a durable instance (Priority: P1)

A conductor turn ends with remaining work (ledger not all `done`, abort, or confirmation that times out / never returns). Ze does **not** silently insert a goal or workflow. The user gets a clear offer: keep this going as a goal or as a workflow (one primary, per research). If they accept, companion delegates to the goal or workflow agent with a fat brief of the ledger and `prior_outputs`. If they decline, nothing is stored.

**Why this priority**: Durable escape was explicitly after 154; stall-ask (156) is not enough when the user is gone.

**Independent Test**: Simulate turn end with unfinished ledger → offer, 0 store inserts. Simulate accept → exactly one `create_goal` or `create_workflow` nested tool (via delegate), 152 gated. Decline → 0 inserts.

**Acceptance Scenarios**:

1. **Given** a conductor turn that ends with unfinished specialist work, **When** the user-facing close happens, **Then** Ze offers a goal or workflow instance and does not create one yet.
2. **Given** a pending confirmation that times out or never returns, **When** that timeout path runs, **Then** the user is offered promote (notification if offline) and no instance is created without accept.
3. **Given** the user accepts the offer, **When** companion proceeds, **Then** it `delegate_to_agent` to `goals` or `workflow` with the conductor ledger and prior outputs in the brief; companion still speaks.
4. **Given** the user declines, **When** the turn settles, **Then** 0 new goal and 0 new workflow rows exist from that offer.

---

### User Story 2 - “Keep going on this” and multi-session intent (Priority: P1)

The user says to keep going on the current conductor job, or the ask is clearly multi-week / multi-session (thesis, recurring report). Companion offers or, when the user already chose to continue, creates the appropriate instance (goal vs workflow per research). Creating still uses specialist tools and 152 confirmation where those intents require it — “keep going” is not a bypass of goal-create confirm.

**Why this priority**: Explicit user language must not be dropped as another chat turn.

**Independent Test**: Prompt “keep going on this” with a conductor ledger in state → delegate to create path. Multi-week wording without a ledger still follows 142 goal routing (not a second speech-act table).

**Acceptance Scenarios**:

1. **Given** an in-flight or just-finished conductor ledger and the user says keep going, **When** companion runs, **Then** it starts promote (offer if type is ambiguous, else create via delegate still subject to 152).
2. **Given** a clearly multi-week outcome with no need for in-chat remaining steps, **When** routed, **Then** a **goal** instance is the primary door (142 R6), not a procedure.
3. **Given** a repeatable or scheduled job the user wants unattended, **When** promoted, **Then** a **workflow** instance is the primary door, not a goal and not a procedure.

---

### User Story 3 - Procedures and in-chat conductor stay out (Priority: P1)

Promote never writes `memory_procedures`, never activates a procedure (135–139), and never makes the workflow/goal engine the speaker for this chat turn. Parallel independent compound is unchanged. Swarm is unchanged.

**Why this priority**: The pin is easy to violate by “just reuse procedures.”

**Independent Test**: Grep/tests: promote path does not call procedure stores. Conductor rewrite rules from 153/155 still apply for in-chat work that *can* finish this turn.

**Acceptance Scenarios**:

1. **Given** a promote, **When** stores are inspected, **Then** procedure tables are untouched.
2. **Given** a short mixed gather+act that can finish now, **When** it succeeds, **Then** Ze MUST NOT auto-offer promote.
3. **Given** this phase, **When** the user chats, **Then** specialists still do not take the mic; goals/workflows do not become the in-chat conductor.

---

## Edge Cases

- Unfinished because companion asked a clarifying question (156 `ask_user`) **in this reply**: that is not a second promote offer; wait for the answer. If the user leaves without answering (confirmation/session timeout), then offer promote.
- Both goal and workflow fit: ask which; never create both from one offer.
- Goal already exists for the same outcome (phase 71 convergence): do not duplicate; offer to attach/steer if tools exist, else say so.
- Abort mid-delegate: offer with partial `prior_outputs`.
- User accepts offer then denies 152 create confirmation: no row; conductor job stays closed unless they ask again.
- Companion-primary speech-act “help me ship the thesis” with no mixed specialists: 142 goal path, not this promote (no fake conductor ledger).

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: When a conductor job must outlive the turn (unfinished ledger at turn end, abort, confirmation that never returns, user keep-going, clearly multi-session), the system MUST offer or create a **workflow or goal instance**, not a procedure.
- **FR-002**: Auto-create without user accept is forbidden except after an explicit keep-going (or equivalent accept of an offer). Timeout/abort/offline MUST offer (chat and/or notification), not silent insert.
- **FR-003**: Goal vs workflow MUST follow research: multi-week outcome → goal; repeatable/scheduled unattended steps → workflow; ambiguous → ask once. Never both from one promote.
- **FR-004**: Create MUST go through existing goal/workflow specialists via `delegate_to_agent` (151) with fat brief of ledger/`prior_outputs`. Companion MUST NOT import those tools. 152 gates and 113 `request_id` MUST apply.
- **FR-005**: Successful in-turn conductor completion MUST NOT auto-offer promote.
- **FR-006**: 153/155 in-chat conductor, 156 stall/ask, 151/152/154 MUST remain. Goals/workflows MUST NOT replace companion as the in-chat sequencer.
- **FR-007**: This phase MUST NOT write `memory_procedures`, MUST NOT implement procedure activation (135–139), MUST NOT swarm, MUST NOT split parallel graph gates, MUST NOT restore `_execute_compound` sequential.

### Key Entities

- **Promote offer**: User-visible choice to continue this job as one goal or one workflow; recorded on trace (status or flag) so 154-style inspectability remains.
- **Goal instance**: Existing goal engine row (milestones, gates).
- **Workflow instance**: Existing workflow definition/run, not a chat DAG.
- **Same job**: Fat brief includes user prompt, ledger, `prior_outputs` — not an empty “continue later.”

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of tested unfinished/timeout/abort fixtures produce an offer and 0 silent inserts.
- **SC-002**: 100% of tested accepted offers create exactly one goal or one workflow via nested specialist tools.
- **SC-003**: 100% of tested keep-going fixtures start promote without dropping the ledger.
- **SC-004**: 0 procedure writes in promote tests.
- **SC-005**: 100% of tested successful short conductor turns produce 0 promote offers.

---

## Assumptions

- Notification reuse: existing proactive/notification path (105) for offline timeout offers; no new push product.
- Goal agent name remains `goals`; workflow agent remains `workflow` (verify at implement).
- “Clearly multi-session” without conductor rewrite still uses 142, not a second classifier in routing.py.
- 155 and 156 are Implemented before 157 product code.
- Offer UI MAY use existing confirm/component primitives; MUST be visible in the assistant message if the client is connected.

## Out of Scope

- Procedures / `memory_procedures` / 135–139.
- Swarm / specialist-as-speaker.
- Per-subtask parallel gates.
- Rewriting goal/workflow engines to sequence in-chat delegates.

## Verbatim Constraints

- `delegate_to_agent`
- `prior_outputs`
- `create_goal`
- `create_workflow`
- `memory_procedures` (forbidden)
- `conductor_ledger`
- `request_id`
- Principle VIII

## After this feature / Future work

Later: per-subtask gate on independent parallel graph path. Not feeding deleted sequential `_execute_compound`.
