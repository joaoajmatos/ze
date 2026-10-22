# Feature Specification: Unattended Step Runner

**Feature Branch**: `214-unattended-step-runner`

**Created**: 2026-10-22

**Status**: Draft

**Depends on**: 200 (AgentContext derivation), 201 (typed turn services)

**Input**: Architecture review 2026-10-22, candidate C12. One `UnattendedRun` runs both goal milestones and workflow steps and returns Done or Held, so milestones get memory, trace and telemetry. There is one hold path, and one procedure-candidate helper serves both planners. Goals and workflows keep separate lifecycles.

## Context *(verified against the code, 2026-10-22)*

An unattended step runs in two different ways today.

**Goal milestone.** `GoalExecutor._execute_milestone` (`ze_automation/goals/executor.py:884-924`; the module is 1,075 lines):

- It builds an `AgentContext` by hand with `session_id="goal:<id>"`, the prompt, `pre_approved_writes`, `memory_store` and `extensions` (:906-913).
- It calls `agent.run(ctx)` directly under `unattended_workspace` (:915-916).
- So a milestone gets no routing, no `fetch_context` memory retrieval, no timezone, no skills, no judgments, no `MessageTrace`, no telemetry and no `write_memory`.
- It catches parked writes as the `LoopParked` exception (:316, :918) and opens a hold with `open_hold` (:411).

**Workflow step.** The step runs through the whole conversation graph:

- `WorkflowRunner` (`workflow/runner.py`, 136 lines) drives the graph that `ze_api/wiring/workflow_graph.py` (121 lines) builds. It runs `load_workflow_step → resolve_screen → embed_route → … → execute_tool → … → write_memory → verify_step` (:60-110).
- It detects parked writes differently, by inspecting the graph snapshot's interrupts for a `WriteConfirmation` (`open_confirmation`, `runner.py:21-33`), then calls `open_hold` (:89).
- `open_hold` and `HeldWriteResumer` (`holds/resumer.py`, 252 lines) are the shared part, and the good part.

**Planners duplicate procedure logic:**

- `GoalPlanner._fetch_procedures` (`goals/planner.py:507`) returns `list[Procedure]`, and `extract_procedure` is at :469.
- `WorkflowPlanner._fetch_procedures` (`workflow/planner.py:160`) returns a formatted `str`, and `extract_procedure` is at :180.
- The extraction prompts are near copies (`goals/planner.py:161-176`, `workflow/planner.py:60-`).

**Blast radius** (`graphify affected GoalExecutor`): ze-automation `__init__`, `agents/goals/agent.py`, five goal tools (`steer_goal`, `pause_goal`, `resume_goal`, `abandon_goal`, and others), and `bootstrap.build_automation_stack`. `WorkflowRunner` and `open_hold` are internal to ze-automation and ze-api wiring.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A goal milestone knows what Ze knows (Priority: P1)

When Ze works on a goal milestone overnight, the agent sees the same memory, the same timezone and the same skills it would see in chat. The result is remembered and explained the same way: trace, telemetry and memory write.

**Why this priority**: a milestone today runs with only the prompt the executor writes, so it can contradict facts Ze already holds and leaves no trace to explain itself.

**Independent Test**: run one milestone through `UnattendedRun` with a fake agent and a fake memory store that holds one relevant fact. Assert that the agent's context carried the fact and the user's timezone, and that a trace was recorded.

**Acceptance Scenarios**:

1. **Given** the user said "I'm vegetarian" and a goal milestone plans meals, **When** the milestone runs, **Then** the fact reaches the agent through normal retrieval.
2. **Given** a milestone ran, **When** the user opens the goal's step log, **Then** each run links to a trace with its tool calls and cost.

---

### User Story 2 - A write that was not pre-approved waits for the user, the same way in goals and workflows (Priority: P1)

When an unattended step wants a write that was not pre-approved, the run stops, opens one held write and sends one push, through one hold path whether the step belongs to a goal or a workflow.

**Why this priority**: with two detection paths (an exception for goals, snapshot inspection for workflows), a change to one silently breaks the other.

**Independent Test**: run a goal milestone and a workflow step that each request the same unplanned write, and assert identical held-write records and identical push calls.

**Acceptance Scenarios**:

1. **Given** a milestone that tries to send an email that was not pre-approved, **When** it runs, **Then** the result is Held, with one held write and one `write_approval_held` push.
2. **Given** the user approves the held write, **When** the resumer resumes it, **Then** the same step continues and finishes as Done.

---

### User Story 3 - Both planners propose procedures the same way (Priority: P3)

Goal and workflow planning find relevant procedures through one helper. Completed goals and workflows propose procedure candidates through one extraction path.

**Independent Test**: plan a goal and a workflow against the same fake procedure store, and assert the same procedures were offered.

**Acceptance Scenarios**:

1. **Given** a validated procedure that matches both descriptions, **When** a goal and a workflow are planned, **Then** both planners see it in the same format.

### Edge Cases

- **A step's agent no longer exists** (renamed or disabled): the run fails with a clear reason, without silently falling back to the companion as the goal executor does today (`executor.py:891-893`). Whether to fall back is open; see Assumptions.
- **Steering arrives while a milestone runs.** The goal lifecycle keeps its steering queue; the step runner is not involved.
- **A held write expires.** The step result reports expiry to the owner's lifecycle (goal or workflow), which decides what happens next.
- **The workspace is unavailable** to unattended runs: the same `unattended_workspace` rule applies to both.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide one unattended step runner that takes an owner (goal milestone or workflow step), a prompt or step, a target agent and the step's pre-approved writes, and returns `Done(result)` or `Held(confirmation)`.
- **FR-002**: The runner MUST run the step through the same per-turn pipeline as a conversation turn: memory retrieval, skills, routing to the named agent, the trace, telemetry and the memory write. It uses the turn context derivation from phase 200 (`for_unattended`).
- **FR-003**: The runner MUST detect a parked write one way for both owners, and open exactly one held write per stop through `open_hold`.
- **FR-004**: Goal and workflow lifecycles stay separate. Milestones, gates, replanning and steering stay in the goal module. Schedules, branches, retries and `on_failure` stay in the workflow module.
- **FR-005**: One procedure-candidate helper MUST serve both planners, for discovery and for extraction from a completed run, with one return shape.
- **FR-006**: The goal executor MUST NOT build an `AgentContext` by hand.
- **FR-007**: Every step run MUST produce one action record citing its owner, as phase 136 requires.
- **FR-008**: Pre-v1 hard cut. The old milestone path and snapshot-specific hold detection are deleted in this phase.

### Key Entities

- **Unattended step**: one unit of work Ze runs without the user present, owned by a goal milestone or a workflow step.
- **Step result**: Done (with response and tool calls) or Held (with the confirmation that waits on the user).
- **Procedure candidate**: a proposed reusable how-to, extracted from a completed goal or workflow.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of goal milestone runs record a trace and a cost, against 0% today.
- **SC-002**: One parametrized test drives a goal milestone and a workflow step through the same held-write scenario, and both pass with identical hold records.
- **SC-003**: `goals/executor.py` shrinks by at least the context building, the agent dispatch and the procedure helpers (more than 150 lines), with no change to the goal lifecycle tests.
- **SC-004**: Planner procedure discovery exists in exactly one module.

## Assumptions

- Phases 200 and 201 have landed, so a typed per-turn services object and context derivation exist to reuse.
- Workflow steps already run through the graph. The runner may wrap the workflow graph's step path rather than build a new pipeline, and the plan decides which.
- **Open:** whether a milestone whose `agent_hint` names a missing agent should fall back to the companion (today's behaviour) or fail. The default in this spec is to keep the fallback and log it.
- Goal milestones go through routing only to the agent the milestone names. They do not use free routing.
