# Feature Specification: Workspace Runs Module

**Feature Branch**: `215-workspace-runs-module`

**Created**: 2026-10-22

**Status**: Draft

**Depends on**: 201 (typed turn services)

**Input**: Architecture review 2026-10-22, candidate C13. One `WorkspaceRuns` module owns start, short wait, detach, complete, reattach and the busy refusal. Tools take it as an injected dependency, and the module globals and `configure()` are deleted. The gate runs once, and the fallback with no store is bounded. The chat-first workspace rules from phase 161 stay.

## Context *(verified against the code, 2026-10-22)*

The run lifecycle is split across two modules.

**A tool helper in `ze_workspace/tools.py` (527 lines):**

- `_run_and_maybe_detach` (:240-296) inserts the in-progress run (`_record_run`, :142), dispatches it, polls up to the short wait (`_poll_get_run`, :199-230), and then either completes it or hands it to the watcher, and touches `used`.
- It also returns the "still running" reply.

**`RunWatcher` in `ze_workspace/followthrough.py` (225 lines):**

- `detach` (:93), `reattach` (:106), `cancel` (:150), `_watch_to_terminal` (:168), `_complete_from_status` (:202).
- It completes detached and reattached runs and starts the follow-up turn.

**Module-level mutable state** breaks the AGENTS.md rule against module globals that hold state:

- `tools.py` keeps eight: `_client`, `_gate`, `_store`, `_settings`, `_ingestion`, `_skill_store`, `_run_watcher`, `_short_wait_seconds` (:37-45). They are set by `configure()` (:48-76).
- `configure()` is called twice: first in `ze_workspace/bootstrap.py:94`, then again in `ze_api/wiring/container.py:581` to add the ingestion pipeline and the skill store. Callers must remember that order.
- `action_handoff.py:23-33` adds `_action_store` and `_workspace_store`, set by `configure_action_ledger`.

**The gate runs twice per write:**

- once in `workspace_ask_check` (:122-134), which decides whether to ask first;
- again in each tool body through `_decide` (:86-95), for example `workspace_write` at :342-344.

**The fallback with no store has a different contract.** When `_store is None`, `_run_and_maybe_detach` polls with `deadline_seconds=None`, which has no time bound (:255-258).

**Blast radius** (`graphify affected RunWatcher`):

- `ze_api/api/v0/workspace/router.py` (`cancel_workspace_run`, :266)
- `ze_api/wiring/container.py` (`_ContainerTurnStarter`, `_NotifierPushSender`, `ZeContainer`)
- `ze_workspace/bootstrap.py`

`ze_workspace.tools` is imported by `ze_workspace/bootstrap.py:56,94` and by `ze_api/wiring/container.py:579`. `base_agent.py:67` names the tools only.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A long command behaves the same whether it finishes quickly or not (Priority: P1)

The user asks Ze to run a command in the workspace. If it finishes within the short wait, Ze replies with its output. If not, Ze says it is still running, follows up in the same thread when it ends, and pushes if the user is offline. This is all phase 116 behaviour, now owned by one module.

**Why this priority**: this is the user-facing contract of the workspace, and today it is split between a tool helper and a watcher with different completion paths.

**Independent Test**: drive `WorkspaceRuns` with a fake sidecar client in three cases: finishes in time, finishes after detach, and the server restarts mid-run (reattach). Assert one run record per case, and the right ending.

**Acceptance Scenarios**:

1. **Given** a command that ends in 3 seconds, **When** the user runs it, **Then** the reply carries its output and the run is recorded once as complete.
2. **Given** a command that runs for 2 minutes, **When** the user runs it, **Then** Ze replies "still running", and later sends one follow-up turn with the result.
3. **Given** Ze restarts while a run is detached, **When** it starts, **Then** the run is reattached and finishes once.
4. **Given** a run is already in progress, **When** the user starts another, **Then** Ze refuses with the busy message from phase 129.

---

### User Story 2 - The workspace decides once whether to ask (Priority: P2)

For each workspace action, the gate is consulted exactly once, and its answer drives both the ask-first decision and the refusal.

**Why this priority**: two decisions per call can disagree if the context changes between them, and the rule then lives in two places.

**Independent Test**: count gate calls for one `workspace_write` and assert exactly one.

**Acceptance Scenarios**:

1. **Given** an unattended run in which the gate denies writes, **When** a write is attempted, **Then** it is refused, and the gate was asked once.

---

### User Story 3 - Workspace tools can be tested without global setup (Priority: P2)

Each workspace tool receives the runs module and the gate as injected dependencies (the `@tool` injection from phase 181). Tests build fakes per test, and nothing leaks between tests.

**Independent Test**: run two tool tests in either order with different fake clients and assert no cross-talk.

**Acceptance Scenarios**:

1. **Given** the workspace is not configured, **When** a workspace tool is called, **Then** it reports "workspace unavailable" from its dependency, not from a missing global.

### Edge Cases

- **The sidecar is unreachable at dispatch.** The run is recorded as failed with `sidecar_dispatched=false`, and no watcher starts.
- **No run store is configured** (tests, minimal setups). The run is still bounded by the short wait and the run's own timeout, and never polls without a limit.
- **Cancel arrives during the short wait.** The run ends as cancelled, and the tool's reply says so.
- **The follow-up turn fails.** The run stays complete, and the failure is logged. It is not retried forever.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide one workspace-runs module that owns starting a run, the short wait, detaching, completing, reattaching after restart, cancelling, and the one-run-at-a-time busy refusal.
- **FR-002**: The run-journal invariants MUST live only in that module: one in-progress run, the `ended_at IS NULL` guard and `sidecar_dispatched`.
- **FR-003**: Workspace tools MUST receive the runs module, the client and the gate as injected dependencies. They only format results.
- **FR-004**: `ze_workspace.tools` MUST hold no module-level mutable state. `configure()` and `configure_action_ledger()` are deleted, and so is the second configuration call in ze-api wiring.
- **FR-005**: The workspace gate MUST be consulted once per tool call. The ask-first check and the tool body share that one decision.
- **FR-006**: Every run, with or without a run store, MUST be bounded by the short wait and the run's timeout.
- **FR-007**: The chat-first rules from phase 161 hold: no execution modes; unattended runs always have the computer; the Governance › Files map stays read-only.
- **FR-008**: The workspace action-record handoff MUST receive its stores by injection. It writes one action record per run, as today.
- **FR-009**: Pre-v1 hard cut. `_run_and_maybe_detach`, `_record_run` and the globals are deleted, not wrapped.

### Key Entities

- **Workspace run**: one command run on Ze's isolated computer. It is in progress, complete, failed, timed out or cancelled, and it records its origin (conversation or unattended).
- **Run journal**: the durable record of workspace runs, which lets Ze reattach after a restart.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A grep finds zero `global` statements in `ze_workspace/` non-test code.
- **SC-002**: Exactly one gate decision per workspace tool call, asserted for every write tool.
- **SC-003**: The three run paths (in time, detached, reattached) are covered by tests through the runs module's interface alone, without tool-module globals.
- **SC-004**: No code path polls the sidecar without a time bound.

## Assumptions

- Phase 201's typed turn services exist, so the runs module reaches the per-turn origin and thread id through them, not through context variables read inside tools. If 201 keeps context variables for these, the module reads them in one place.
- `ze_skills.tools.configure` has the same global pattern. It is noted for the plugin-seam or skills work and is out of scope here.
- The script runner (`ze_workspace/scripts.py`, phase 197) is unchanged.
