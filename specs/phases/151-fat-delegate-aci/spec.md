# Feature Specification: Fat Delegate ACI

**Feature Branch**: `151-fat-delegate-aci`

**Created**: 2026-09-16

**Status**: Ready to implement

**Input**: User description: "151 Fat delegate ACI: Upgrade `delegate_to_agent` (objective, prior outputs/inputs, output shape, stop). Nested `tool_calls` preserved for 146 honesty. Only companion may call it; max depth 1. Research loses the tool. Do not change conversation graph, companion embedding `description`, or `plan_sequential`. Speech-act one-shot delegates must keep working."

**Governed by**: [`specs/arch/companion-conductor-roadmap.md`](../../arch/companion-conductor-roadmap.md) (phase 151), [`specs/arch/pre-v1-hard-cuts.md`](../../arch/pre-v1-hard-cuts.md) (Principle VIII), [`specs/arch/ze-doctrine.md`](../../arch/ze-doctrine.md), nested-delegate honesty [`146-forget-vs-cancel`](../146-forget-vs-cancel/spec.md), speech-act routing [`142-speech-act-routing`](../142-speech-act-routing/spec.md). Plugin code imports `ze_sdk` / owning plugin, never `ze_core`. Companion MUST NOT import calendar or messenger tools.

**Depends on**: Phase 146 nested `{response, tool_calls}` result. Phase 142 one-shot speech-act delegates.

**Does not start**: Phase 152 (per-delegate capability), 153 (sequential routing), 154 (observability). Number 151 here is the conductor series, not memory-honesty roadmap item 151 (already bundled into phase 150).

---

## Overview

Companion already hands work to specialists with a thin brief (`agent_name` + `task` + optional `context`). Research also lists that tool and is allowed to nest two levels. That is not a conductor: briefs are too thin for later sequential work, and a second speaker can re-delegate.

This phase upgrades the **same** `delegate_to_agent` tool so companion can pass a fat brief (objective, prior outputs and inputs, output shape, stop). Workers stay isolated: fat brief in, structured result plus nested tool records out. Only companion may call the tool. Depth is one. Research loses it. Speech-act one-shot handoffs keep working with the new required field names. Nested `tool_calls` stay the honesty surface for 146. The conversation graph, companion embedding `description`, and `plan_sequential` stay unchanged.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Companion can brief a specialist with a fat ACI (Priority: P1)

The user asks companion to do work that needs a specialist (including today’s speech-act one-shots: remind me, close a loop, cancel a reminder). Companion calls `delegate_to_agent` with a named specialist and a fat brief: what to achieve, any prior outputs or extra inputs, the shape of the answer, and when to stop. The specialist runs in isolation and returns a structured result. Companion still speaks to the user. The specialist transcript is not dumped into the session message list.

**Why this priority**: 153 cannot sequence mixed turns until briefs are good enough; 142/146 already depend on this tool.

**Independent Test**: Unit-test `run_delegate` with the new arguments. Speech-act companion prompts still produce a successful one-shot delegate to reminders/loops/goals. Result is `{response, tool_calls}` as in 146, not a string. Session `messages` for the parent do not grow with the worker’s inner chat.

**Acceptance Scenarios**:

1. **Given** companion is the parent agent, **When** it calls `delegate_to_agent` with `agent_name`, `objective`, and optional `prior_outputs`, `inputs`, `output_shape`, `stop_condition`, **Then** the specialist runs with a prompt assembled from those fields and returns `{response, tool_calls}`.
2. **Given** a speech-act one-shot (timed remind / cancel reminder / close loop / abandon goal), **When** companion delegates with `agent_name` plus `objective` only, **Then** the specialist still runs and nested `tool_calls` still earn 146 domain confirmations.
3. **Given** a successful delegate, **When** the parent inspects the tool result, **Then** `tool_calls` is the specialist’s nested list (not omitted), and `task` / `context` are not accepted as a second ACI.
4. **Given** the worker ran, **When** the session history is read, **Then** the specialist’s inner messages are not appended to session `messages`.

---

### User Story 2 - Only companion conducts; specialists cannot re-delegate (Priority: P1)

Research and other specialists no longer list `delegate_to_agent`. A worker at depth 1 cannot call it even if a prompt asks. Companion is the only in-chat caller. Max depth is 1 (companion → specialist).

**Why this priority**: One conductor is a pinned product rule, not a later cleanup.

**Independent Test**: Research `tools` omit `delegate_to_agent`. `run_delegate` from a non-companion parent fails closed. Depth 1 (already inside a worker) fails closed without invoking another agent. Graph routing is unchanged.

**Acceptance Scenarios**:

1. **Given** research’s tool list after this phase, **When** it is inspected, **Then** `delegate_to_agent` is absent.
2. **Given** research needs calendar data, **When** it replies, **Then** it does not call `delegate_to_agent`; it says it needs the calendar agent (or states the limitation) rather than guessing the calendar.
3. **Given** `run_delegate` is invoked with parent intent/agent other than companion, **When** it executes, **Then** it returns a failed tool call and does not run the specialist.
4. **Given** a specialist already running as a delegate (depth 1), **When** it would call `delegate_to_agent`, **Then** the call fails at the depth cap of 1 and does not start a second specialist.

---

### User Story 3 - This phase does not steal routing or graph sequence (Priority: P2)

Mixed calendar-then-email turns still follow today’s graph (including sequential `plan_sequential` → END). Companion embedding `description` is unchanged so routing scores do not shift. Independent parallel compound is untouched.

**Why this priority**: Bundling ACI with routing is the failure mode the roadmap split exists to prevent.

**Independent Test**: Diff conversation graph nodes/edges: `plan_sequential` still present. Companion `description` string unchanged. No `is_sequential` → companion primary rewrite.

**Acceptance Scenarios**:

1. **Given** this phase ships, **When** a sequential compound envelope is produced, **Then** `after_decompose` still routes to `plan_sequential` (not companion-as-primary).
2. **Given** companion’s class `description`, **When** this phase ships, **Then** that embedding text is byte-for-byte unchanged.
3. **Given** capability inheritance, **When** `run_delegate` builds the worker context, **Then** it still copies the parent `gate_decision` (152 owns per-delegate gates).

---

## Edge Cases

- Empty `objective`: fail the tool call; do not run the specialist.
- Unknown `agent_name`: fail as today; do not invent a peer swarm.
- Companion delegates to companion: fail closed (not a legal worker).
- Optional fat fields omitted: equivalent to today’s one-shot brief (objective only).
- Specialist lists `delegate_to_agent` in `tools`: must not remain after this phase; tests fail if any agent other than companion lists it.
- Abort token: still inherited so a top-level abort stops the worker.
- 146 string-only `result`: remains deleted; do not reintroduce.
- Research tests that stub `delegate_to_agent`: delete or rewrite; do not leave a shim list.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST hard-cut `delegate_to_agent` arguments to required `agent_name` and `objective`, plus optional `prior_outputs`, `inputs`, `output_shape`, and `stop_condition`. `task` and `context` MUST be removed in this phase (callers updated; no dual ACI).
- **FR-002**: System MUST assemble an isolated worker prompt from those fields (fat brief in) and MUST return `ToolCall.result` as `{response, tool_calls}` (146). Session `messages` MUST NOT receive the specialist transcript.
- **FR-003**: System MUST allow `delegate_to_agent` only on companion’s tool list. Research and every other agent MUST NOT list it.
- **FR-004**: System MUST refuse `run_delegate` when the parent is not companion, or when the target is companion, or when delegate depth would exceed 1.
- **FR-005**: System MUST keep speech-act one-shot delegates working using `agent_name` + `objective` (reminders, loops, goals) with nested `tool_calls` still earning 146 confirmations.
- **FR-006**: Research instructions MUST stop telling the model to call `delegate_to_agent` for calendar; they MUST tell it to say it needs the calendar agent (or state the limitation) instead of guessing.
- **FR-007**: This phase MUST NOT change the conversation graph, MUST NOT change companion `description`, MUST NOT delete or wrap `plan_sequential` / `dynamic_plan_steps`, MUST NOT implement per-delegate `CapabilityGate` (152), sequential routing to companion (153), promote-to-workflow/goal, or specialist-as-speaker.
- **FR-008**: System MUST keep inheriting the parent `gate_decision` on the worker context in this phase (152 replaces that).

### Key Entities

- **Fat brief**: The ACI payload companion sends: objective, optional prior outputs, inputs, output shape, stop condition.
- **Isolated worker run**: One specialist `run` with a fresh messages list built from the brief, not the parent transcript.
- **Nested tool_calls**: The specialist’s `AgentResult.tool_calls` copied into the parent `delegate_to_agent` result for honesty gates.
- **Conductor**: Companion as the only legal `delegate_to_agent` caller. Not a graph node in this phase.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of tested companion delegates, the tool schema and `run_delegate` accept `objective` and reject `task`/`context`.
- **SC-002**: In 100% of tested speech-act one-shots after the rename, nested domain tools still earn 146 confirmations.
- **SC-003**: 100% of non-companion agents have `delegate_to_agent` absent from `tools`; 100% of tested non-companion `run_delegate` calls fail without starting a specialist.
- **SC-004**: Delegate depth greater than 1 is 0% successful in tests (cap is 1).
- **SC-005**: Graph tests still route sequential compound to `plan_sequential`; companion `description` is unchanged.

---

## Assumptions

- `prior_outputs` is a string (serialized prior specialist text or ids). Structured JSON is allowed inside the string; this phase does not add a typed DAG.
- `inputs` is a string for extra facts (event id, recipient, constraints). Not a shared blackboard.
- `output_shape` and `stop_condition` are free-text hints to the worker, not an executable planner.
- Depth 0 is companion; the worker is depth 1. Cap is “no nested delegate,” not “zero delegates.”
- Abort, reporter, memory, persona, and contacts still pass through as today except where FR-004 refuses the call.
- Eval scenarios for sequential calendar-then-email are phase 154.

## Out of Scope

- Per-delegate capability and confirmation (152).
- Sequential / mixed routing to companion; deleting `plan_sequential` (153).
- Trace panel, progress keys, eval scenarios (154).
- Promote to workflow/goal.
- Swarm / specialist-as-speaker / shared chat blackboard.
- Companion importing calendar or messenger tools.
- Changing companion embedding `description`.

## Verbatim Constraints

- `delegate_to_agent`
- `agent_name`
- `objective`
- `prior_outputs`
- `inputs`
- `output_shape`
- `stop_condition`
- `tool_calls`
- `response`
- `plan_sequential`
- `dynamic_plan_steps`
- `description` (companion class attribute — unchanged)
- `_DELEGATE_MAX_DEPTH` equivalent: max depth **1**
- `gate_decision` (still inherited this phase)
- Principle VIII (no shim, no dual ACI)

## After this feature / Future work

[`companion-conductor-roadmap.md`](../../arch/companion-conductor-roadmap.md): 152 per-delegate gate, 153 routing hard-cut, 154 observability. Do not start 152 in this tree.
