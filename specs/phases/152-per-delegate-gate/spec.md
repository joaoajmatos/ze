# Feature Specification: Per-Delegate Capability and Confirmation

**Feature Branch**: `152-per-delegate-gate`

**Created**: 2026-09-16

**Status**: Ready to implement

**Input**: User description: "152 Per-delegate capability and confirmation: Stop inheriting parent `gate_decision` wholesale. Evaluate specialist+intent at each `run_delegate`. Write confirmation pauses conductor loop and resumes; a lookup in the same turn is not held for a later send. Graph parallel compound may keep strictest-wins (out of 152)."

**Governed by**: [`specs/arch/companion-conductor-roadmap.md`](../../arch/companion-conductor-roadmap.md) phase 152, [`specs/arch/pre-v1-hard-cuts.md`](../../arch/pre-v1-hard-cuts.md), [`specs/arch/ze-doctrine.md`](../../arch/ze-doctrine.md), confirmation keying [`113-hardening-sweep`](../113-hardening-sweep/spec.md), fat ACI [`151-fat-delegate-aci`](../151-fat-delegate-aci/spec.md). Plugin code imports `ze_sdk` / owning plugin, never `ze_core`. Companion MUST NOT import calendar or messenger tools.

**Depends on**: Phase 151 (companion-only fat `delegate_to_agent`, depth 1, nested `tool_calls`). Phase 113 (`pending_confirmations` keyed by `request_id`).

**Does not start**: Phase 153 (sequential routing / delete `plan_sequential`), 154 (trace panel / eval).

---

## Overview

Today a nested specialist inherits the parent turn’s `gate_decision`. Companion is autonomous, so a worker can send mail or create events under EXECUTE even when that specialist’s own intent would wait for confirmation. Graph compound still takes the strictest decision across all subtasks, which also holds an independent lookup because a later write exists.

This phase gates **each** `run_delegate` on that specialist plus an inferred or declared intent, composed with spend budget the same way the graph already does. A confirmation pauses the conductor and resumes it for that invocation. A calendar lookup in the same turn is not held because a later send would be. Graph **parallel** fan-out may keep strictest-wins; that path is not this phase.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Each specialist invocation has its own gate (Priority: P1)

Companion looks up the calendar (read) then wants a later write specialist. The lookup runs now. The write is gated as that specialist’s write intent, not as companion’s autonomous chat intent. Spend over budget still holds like the existing session/day ceiling.

**Why this priority**: Inherited EXECUTE is how mixed turns become unsafe before 153 even routes them to companion.

**Independent Test**: Stub `CapabilityGate`: calendar `read` → EXECUTE, messenger or calendar write intent → AWAIT_CONFIRMATION or DRAFT. One companion turn with two `run_delegate` calls: first lookup completes; second does not inherit EXECUTE from the parent.

**Acceptance Scenarios**:

1. **Given** parent `gate_decision` is EXECUTE (companion), **When** companion delegates a specialist whose evaluated decision is EXECUTE, **Then** the worker runs immediately with that decision (not a copied parent field as the sole source).
2. **Given** the same parent EXECUTE, **When** companion delegates a specialist whose evaluated decision is DRAFT, **Then** the worker runs in DRAFT (writes suppressed as today) and the earlier lookup in the turn is unaffected.
3. **Given** spend budget would exceed the configured ceiling, **When** `run_delegate` evaluates, **Then** the invocation is held at AWAIT_CONFIRMATION (strictest with the specialist decision), same idea as graph `capability_check`.
4. **Given** graph parallel compound with mixed read+write subtasks, **When** this phase ships, **Then** that path may still use strictest-wins (explicitly out of scope to change).

---

### User Story 2 - Confirmation pauses the conductor, then resumes (Priority: P1)

A specialist invocation needs user confirmation. The conductor stops. The user sees a confirmation keyed by `request_id`. After approve, that specialist runs and companion continues; it does not skip the rest of the sequence. Deny stops that invocation; companion may ask or stop without silently running the write.

**Why this priority**: Roadmap pin 7 — gate the invocation, keep 113 request_id keys.

**Independent Test**: `run_delegate` with AWAIT_CONFIRMATION does not start the worker until approve. A second independent lookup earlier in the loop already returned. After resume, the confirmed specialist runs with EXECUTE for that invocation only.

**Acceptance Scenarios**:

1. **Given** `run_delegate` evaluates AWAIT_CONFIRMATION, **When** the tool is called, **Then** the specialist `run` has not started, a pending confirmation exists under `request_id`, and the conductor loop is paused.
2. **Given** the user approves that `request_id`, **When** the turn resumes, **Then** that specialist invocation runs and companion can call a later delegate.
3. **Given** the user denies, **When** the turn resumes, **Then** the write did not execute; companion does not claim it did.
4. **Given** two concurrent confirmations on one thread, **When** the user answers one, **Then** the other is not cleared (113 `request_id` keying).

---

### User Story 3 - Declared or default intent, not a second planner (Priority: P2)

Companion may pass an optional `intent` on `delegate_to_agent` (calendar `read` vs `create`). If omitted, the system uses that agent’s default intent/mode mapping already used by `CapabilityGate`. This is not a pre-plan of the whole turn and not an executable DAG.

**Why this priority**: Wrong intent would reintroduce inherited EXECUTE in disguise.

**Independent Test**: Same specialist, `intent=read` vs `intent=create` yield different `GateDecision`s matching `CapabilityGate.evaluate`.

**Acceptance Scenarios**:

1. **Given** optional `intent` on the fat ACI, **When** present and known on the agent, **Then** evaluation uses that intent.
2. **Given** omitted `intent`, **When** evaluating, **Then** `CapabilityGate`’s existing default (class `default_mode` / missing intent) applies — no new NL classifier required this phase.
3. **Given** this phase, **When** companion still omits `intent` on speech-act one-shots, **Then** those delegates still run (151) under the specialist default.

---

## Edge Cases

- Unknown declared `intent`: same as `CapabilityGate` today (default mode / confirm), not a crash.
- BLOCKED specialist: failed `ToolCall`; conductor is not paused for confirmation.
- Abort during pause: existing abort token still wins.
- Graph `capability_check` for a companion-primary turn remains companion’s own gate (153); nested path is this phase.
- Do not change messenger/calendar Mode tables here (email `create` may still be DRAFT_ONLY); the rule is per-invocation evaluation, not retuning specialist modes.
- Depth 1 / companion-only rules from 151 stay.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST NOT copy the parent `gate_decision` as the worker’s sole gate. Each `run_delegate` MUST evaluate `CapabilityGate` for that specialist and intent, composed with spend budget (strictest-wins between those two, matching graph `capability_check`).
- **FR-002**: System MUST run EXECUTE workers immediately; MUST run DRAFT workers in DRAFT; MUST fail BLOCKED without starting a write; MUST NOT hold an EXECUTE lookup because a later invocation in the same turn would be DRAFT or AWAIT_CONFIRMATION.
- **FR-003**: When the evaluated decision is AWAIT_CONFIRMATION, the system MUST pause the conductor without starting that specialist `run`, persist confirmation by `request_id` (phase 113), and on approve resume so that invocation runs with EXECUTE.
- **FR-004**: System MUST keep concurrent confirmations on one thread isolated by `request_id` (no thread_id-only clobber).
- **FR-005**: System MUST accept optional `intent` on `delegate_to_agent` without removing 151 fields (`objective`, `prior_outputs`, `inputs`, `output_shape`, `stop_condition`). Omit `intent` MUST remain valid.
- **FR-006**: `run_delegate` MUST obtain the gate through an injected protocol/callback wired by the engine. `ze-agents` MUST NOT import `ze_core`. Companion MUST NOT import calendar or messenger tools.
- **FR-007**: This phase MUST NOT change graph parallel compound to per-subtask gates, MUST NOT delete `plan_sequential`, MUST NOT change companion embedding `description`, MUST NOT promote to workflow/goal, MUST NOT implement 154 trace/eval.

### Key Entities

- **Delegate gate decision**: The `GateDecision` for one `run_delegate` (specialist + intent + budget).
- **Invocation confirmation**: A 113 pending confirmation for one specialist invocation, keyed by `request_id`.
- **Declared intent**: Optional `intent` string on the fat ACI.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of tested turns with an EXECUTE lookup then a non-EXECUTE write delegate, the lookup completed before the write was confirmed or drafted.
- **SC-002**: In 100% of tested AWAIT_CONFIRMATION delegates, the specialist `run` count is 0 until approve, then 1.
- **SC-003**: In 100% of tested dual `request_id` confirmations on one thread, answering one does not delete the other.
- **SC-004**: Graph parallel strictest-wins tests from before this phase still pass unchanged.

---

## Assumptions

- Specialist Mode tables are unchanged (calendar `create` is CONFIRM; messenger `create` may be DRAFT_ONLY).
- Pause/resume uses the existing confirmation + graph interrupt machinery rather than a second bus.
- 151 is Implemented before this tree’s product code (specify-now is allowed; implement-later is ordered).
- Optional `intent` values are the specialist’s existing intent keys (`read`, `create`, …).

## Out of Scope

- Sequential routing to companion; deleting `plan_sequential` (153).
- Trace panel and eval scenarios (154).
- Per-subtask gate on graph parallel compound.
- Promote to workflow/goal.
- Swarm / specialist-as-speaker.

## Verbatim Constraints

- `run_delegate`
- `gate_decision`
- `CapabilityGate`
- `request_id`
- `intent` (optional tool argument added this phase)
- `delegate_to_agent`
- `AWAIT_CONFIRMATION`
- `EXECUTE`
- `DRAFT`
- `BLOCKED`
- Principle VIII

## After this feature / Future work

153 sequential routing hard-cut. 154 observability. Parallel graph per-subtask gate is after 154.
