---

description: "Task list for Workspace Follow-Through"
---

# Tasks: Workspace Follow-Through

**Input**: Design documents from `/specs/phases/116-workspace-follow-through/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/workspace-followthrough-api.md, quickstart.md

**Tests**: Included — Constitution V (Test Discipline) is NON-NEGOTIABLE for this project; every task below that changes behavior ships with a test in the same phase.

**Organization**: Tasks are grouped by user story (spec.md priorities: US1/US2/US3 = P1, US4 = P2) so each can be implemented and validated independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: Maps the task to spec.md's US1–US4
- File paths are exact, per plan.md's Project Structure

## Path Conventions

Existing monorepo layout (plan.md): `core/ze-workspace/ze_workspace/`,
`core/ze-workspace/tests/`, `apps/ze-api/ze_api/`, `apps/ze-api/tests/`,
`apps/ze-web/src/`, `core/ze-core/ze_core/`, `core/ze-automation/`.

---

## Phase 1: Setup

**Purpose**: Configuration this feature needs before any story can run.

- [X] T001 Add `follow_through_short_wait_seconds` (default `25`) to the `workspace:` block in `apps/ze-api/config/config.yaml` and its `ZeApiSettings` mapping in `apps/ze-api/ze_api/settings.py` (research.md D6)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared primitives every user story calls — turn lock, watcher
skeleton, store/client extensions, migration. No user story can be implemented
without these.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 Migration `zws002_run_followthrough.py`: add `follow_through_notified BOOLEAN NOT NULL DEFAULT false` to `workspace_runs`, `depends_on` `zws001`, in `core/ze-workspace/ze_workspace/migrations/versions/zws002_run_followthrough.py`; register the revision in `apps/ze-api/ze_api/migrate.py`'s `_ZE_WORKSPACE_VERSIONS`
- [X] T003 [P] Add `follow_through_notified: bool` to the `WorkspaceRun` dataclass in `core/ze-workspace/ze_workspace/types.py`
- [X] T004 [P] Add `WorkspaceStore.list_in_progress()` (rows with `ended_at IS NULL`) and `WorkspaceStore.mark_follow_through_notified(run_id)` (idempotent `UPDATE ... WHERE follow_through_notified = false`) in `core/ze-workspace/ze_workspace/store.py`
- [X] T005 [P] Add `WorkspaceClient.cancel(run_id)` calling the sidecar's `/cancel` in `core/ze-workspace/ze_workspace/client.py`
- [X] T006 [P] Implement `ThreadTurnLock` (`dict[str, asyncio.Lock]` keyed by `thread_id`, `acquire`/`release` async context manager) in `core/ze-workspace/ze_workspace/turn_lock.py`
- [X] T007 Implement `TurnStarter`/`PushSender` Protocols and the `RunWatcher` skeleton (`detach`, `reattach`, terminal-status handling, `follow_through_notified` guard) in `core/ze-workspace/ze_workspace/followthrough.py` (depends on T003, T004)
- [X] T008 [P] Unit tests for `ThreadTurnLock` acquire/release ordering and per-thread isolation in `core/ze-workspace/tests/test_turn_lock.py`
- [X] T009 [P] Unit tests for `RunWatcher` (detach schedules a task; terminal status triggers `TurnStarter`+`PushSender` exactly once via `follow_through_notified`; `reattach` re-adopts an `ended_at IS NULL` row; origin != conversation never dispatches) with a fake store/turn-starter/push-sender in `core/ze-workspace/tests/test_followthrough.py` (depends on T007)

**Checkpoint**: Foundation ready — user story phases can begin.

---

## Phase 3: User Story 1 - Short work stays in the turn; long work lets go (Priority: P1) 🎯 MVP

**Goal**: A quick workspace command finishes on the same turn; a slow one ends the
turn with a "still running" reply after the short wait, and the run keeps going —
visibly, both in the conversation and on the workspace page.

**Independent Test**: quickstart.md Scenarios 1 and 2 — a command that finishes
inside the short wait returns its result on that turn; a command that outlives it
ends the turn with "still running" and `GET /api/v0/workspace/runs` shows
`ended_at: null`, visible on both the chat thread and the workspace page.

### Tests for User Story 1

- [X] T010 [P] [US1] Integration test: a workspace command finishing within the short wait returns its result on the same turn, no `RunWatcher.detach` call, in `apps/ze-api/tests/api/test_workspace_followthrough.py`
- [X] T011 [P] [US1] Integration test: a workspace command still running after the short wait ends the turn with a "still running" reply within the short-wait bound (SC-002: the caller can send a new message in under 5s of the wait elapsing) and leaves `ended_at IS NULL`, in `apps/ze-api/tests/api/test_workspace_followthrough.py`

### Implementation for User Story 1

- [X] T012 [US1] In the `workspace_run`/`workspace_run_skill_script` tool executors, await the sidecar call with `asyncio.wait_for(short_wait)`; on timeout call `RunWatcher.detach(run, pending_completion)` and return a "still running" tool result instead of blocking, in `core/ze-workspace/ze_workspace/tools.py` (depends on T007, T001)
- [X] T013 [US1] Project `WorkspaceUsageTrace.runs` entries as `status: "in_progress"` for rows with `ended_at IS NULL` (trace-only, never written to `workspace_runs.status`) in `core/ze-core/ze_core/orchestration/nodes/trace.py` (depends on T003)
- [X] T014 [US1] Regression test: Off/Plan modes never reach `RunWatcher.detach` (nothing runs); Ask/Auto-edit only detach after the existing `ToolConfirmationRequired` resume completes, in `core/ze-workspace/tests/test_tools.py` (depends on T012)
- [X] T015 [US1] Build the running-run banner on the Phase 115 workspace page — shows the in-progress detached run's command and started time, sourced from `GET /api/v0/workspace/runs` (`ended_at: null`), in `apps/ze-web/src/entities/workspace/` (query hook) and `apps/ze-web/src/widgets/workspace-management/` (banner component). Satisfies FR-010's "in the workspace view" half; US3's T035 later adds the cancel button to this banner rather than creating it.
- [X] T016 [US1] Render a "still running" chip identifying the run on the message bubble and the workspace trace section — FR-010's "in the conversation" half, in `apps/ze-web/src/entities/message/ui/MessageBubble.tsx` and `apps/ze-web/src/widgets/trace-panel/ui/WorkspaceSection.tsx`
- [X] T017 [P] [US1] vitest for the running-run banner (T015) and the "still running" chip (T016) in `apps/ze-web/src/widgets/workspace-management/*.test.tsx` and `apps/ze-web/src/entities/message/ui/MessageBubble.test.tsx`

**Checkpoint**: User Story 1 is independently functional and testable (wait-then-detach works and is visible in both places; follow-up/push land in US2).

---

## Phase 4: User Story 2 - When it finishes, Ze comes back on that thread (Priority: P1)

**Goal**: A detached run reaching a terminal status starts a follow-up turn on the
originating conversation; a completion push fires only when the client is
disconnected; the follow-up never lands mid another reply.

**Independent Test**: quickstart.md Scenarios 3, 4, and 7 — connected: follow-up
appears, no push; disconnected: push fires and the follow-up is waiting in the
thread; restart mid-run: follow-up still lands once the run finishes.

### Tests for User Story 2

- [ ] T018 [P] [US2] Integration test: detached run succeeds while the client is connected → follow-up turn appears on the thread, `PushSender.send_completion` is a no-op, in `apps/ze-api/tests/api/test_workspace_followthrough.py`
- [ ] T019 [P] [US2] Integration test: detached run succeeds while the client is disconnected → push is sent and the follow-up turn is written to conversation history, in `apps/ze-api/tests/api/test_workspace_followthrough.py`
- [ ] T020 [P] [US2] Integration test: a follow-up waits for an in-progress turn on the same thread (via `ThreadTurnLock`) before starting — does not interrupt mid-reply, in `apps/ze-api/tests/api/test_workspace_followthrough.py`
- [ ] T021 [P] [US2] Integration test: run finished in-turn (never detached) produces no follow-up turn and no completion push, in `apps/ze-api/tests/api/test_workspace_followthrough.py`

### Implementation for User Story 2

- [ ] T022 [US2] Add `ThreadTurnLock` acquisition/release **inside** `ZeContainer.invoke_raw_turn` and `resume_turn` themselves (`apps/ze-api/ze_api/container.py`, `core/ze-core/ze_core/conversation/turn.py`) — the single point where the lock is taken, so the WebSocket turn handler, the eval route, and the new `TurnStarter` adapter (T023) all inherit it automatically through the same call, with no call-site needing its own acquire (depends on T006, T007)
- [ ] T023 [US2] Implement the `TurnStarter` adapter as a thin wrapper around the now lock-aware `ZeContainer.invoke_raw_turn` (T022) — it does **not** acquire `ThreadTurnLock` itself, matching the contract's intent that locking has exactly one owner, in `apps/ze-api/ze_api/container.py` (depends on T022)
- [ ] T024 [US2] Implement the `PushSender` adapter using `ProactiveNotifier`/`NativeAppInterface`'s existing connected-check (`_conn.connected`), in `apps/ze-api/ze_api/container.py`
- [ ] T025 [P] [US2] Regression test confirming the WebSocket turn handler (`apps/ze-api/ze_api/api/websocket/turns.py`) and the eval route (`apps/ze-api/ze_api/api/routes/eval.py`) call the T022-wrapped `invoke_raw_turn` directly with no second `ThreadTurnLock` acquisition at their call sites (a second acquire on the same non-reentrant lock would deadlock), in `apps/ze-api/tests/test_turn_lock_wiring.py` (depends on T022)
- [ ] T026 [US2] Wire a `RunWatcher` instance with the T023/T024 adapters into container bootstrap, in `apps/ze-api/ze_api/container.py` and `apps/ze-api/ze_api/compose.py`
- [ ] T027 [US2] Startup reconciliation: on boot, query `WorkspaceStore.list_in_progress()` and call `RunWatcher.reattach(run)` for each, alongside the existing proactive job registration fan-out, in `apps/ze-api/ze_api/compose.py` (depends on T004, T026)
- [ ] T028 [US2] Compose the synthetic follow-up prompt text per terminal status (succeeded/failed/timed_out/cancelled), in plain language, in `core/ze-workspace/ze_workspace/followthrough.py` (depends on T007)
- [ ] T029 [US2] Guard `RunWatcher` so only `origin == "conversation"` rows dispatch a follow-up turn or push (`unattended` rows use existing unattended-notification behavior — FR-015), in `core/ze-workspace/ze_workspace/followthrough.py` (depends on T028)

**Checkpoint**: User Stories 1 and 2 both work independently — detach, then automatic follow-through, survives a restart.

---

## Phase 5: User Story 3 - Stop work that has let go (Priority: P1)

**Goal**: The user can cancel a detached run without a confirmation prompt; it
stops, is marked cancelled, and is reported as stopped — never as success.

**Independent Test**: quickstart.md Scenario 5 — cancel a long-running command,
confirm `200` + `status: cancelled` within 15s, confirm partial files remain,
confirm a second cancel on the same run returns `409`.

### Tests for User Story 3

- [ ] T030 [P] [US3] Contract test for `POST /api/v0/workspace/runs/{id}/cancel`: success path within 15s (SC-005), `409` on an already-terminal run, `404` on an unknown id, in `apps/ze-api/tests/api/test_workspace_cancel.py`
- [ ] T031 [P] [US3] Unit test: cancelling a detached run's `RunWatcher` task observes the terminal status and runs the normal US2 follow-through path (follow-up says "stopped", not success), in `core/ze-workspace/tests/test_followthrough.py`

### Implementation for User Story 3

- [ ] T032 [US3] Add `POST /api/v0/workspace/runs/{id}/cancel` route (`operation_id: cancelWorkspaceRun`) returning the updated `WorkspaceRunResponse` or `409`/`404`, in `apps/ze-api/ze_api/api/routes/workspace.py` (depends on T005)
- [ ] T033 [US3] Add `follow_through_notified` to `WorkspaceRunResponse` and add the cancel response schema in `apps/ze-api/ze_api/api/schemas.py`
- [ ] T034 [US3] Implement the cancel path in `ze-workspace`: call `WorkspaceClient.cancel()`, persist `status = cancelled`, `ended_at = now()`, leave `files_touched`/`output_preview` as already recorded, in `core/ze-workspace/ze_workspace/store.py` and `core/ze-workspace/ze_workspace/rest.py` (depends on T005)
- [ ] T035 [US3] Confirm cancel bypasses `WorkspaceGate`'s confirm path entirely (FR-009 — no second confirmation), with a regression test in `core/ze-workspace/tests/test_gate.py`
- [ ] T036 [P] [US3] Add a cancel button to the running-run banner built in T015, in `apps/ze-web/src/widgets/workspace-management/`, wired to the new cancel mutation
- [ ] T037 [P] [US3] vitest for the cancel button and the "already finished" error state in `apps/ze-web/src/widgets/workspace-management/*.test.tsx`

**Checkpoint**: User Stories 1–3 all work independently.

---

## Phase 6: User Story 4 - One thing at a time (Priority: P2)

**Goal**: While a detached run is in progress, a second workspace command
(conversational or unattended) is refused with a pointer to what's already
running — never silently interleaved.

**Independent Test**: quickstart.md Scenario 6 — with a detached run outstanding,
a second request is refused and names the running command; once the first run
ends or is cancelled, a new request succeeds.

### Tests for User Story 4

- [ ] T038 [P] [US4] Integration test: a second `workspace_run` call while a detached run is in progress is refused and names the running command, in `apps/ze-api/tests/api/test_workspace_followthrough.py`
- [ ] T039 [P] [US4] Integration test: unattended (goal/workflow) executor skips or waits — does not interleave — while a detached run is in progress, in `core/ze-automation/tests/executors/test_workspace_busy.py`

### Implementation for User Story 4

- [ ] T040 [US4] Extend `WorkspaceGate`'s busy check to query `WorkspaceStore.list_in_progress()` so any `ended_at IS NULL` row (not only a run the calling turn is itself waiting on) counts as busy for `run`/`run_script`, in `core/ze-workspace/ze_workspace/gate.py` (depends on T004)
- [ ] T041 [US4] Surface the busy refusal message with the running command's identity (id + `command`) to conversational callers, in `core/ze-workspace/ze_workspace/tools.py` (depends on T040)
- [ ] T042 [US4] Confirm `ze-automation` goal/workflow executors already routed through `WorkspaceGate` (Phase 115) now see the same busy signal for detached runs and skip/wait rather than error, in `core/ze-automation/ze_automation/goals/executor.py` and `core/ze-automation/ze_automation/workflow/` (depends on T040)

**Checkpoint**: All four user stories are independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Repo-wide consistency and Definition of Done items (constitution's
Development Workflow section).

- [ ] T043 [P] Add `test-workspace` coverage note for the follow-through tests in `docs/testing.md` (extends the Phase 115 entry rather than adding a new target)
- [ ] T044 Update `specs/README.md` index row for phase 116 (status → implemented) and the Phase status table in `CLAUDE.md`
- [ ] T045 Run `make lint` and `make format` across touched packages (`ze-workspace`, `ze-api`, `ze-automation`, `ze-web`)
- [ ] T046 Walk through `specs/phases/116-workspace-follow-through/quickstart.md` Scenarios 1–7 end to end against `make dev-full`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup (T001, used by T012's `wait_for`). Blocks every user story.
- **User Story 1 (Phase 3)**: Depends on Foundational (T007 `RunWatcher`, T003 `follow_through_notified`). No dependency on US2–US4.
- **User Story 2 (Phase 4)**: Depends on Foundational (T006 `ThreadTurnLock`, T007 `RunWatcher`). Consumes the `RunWatcher.detach` call US1 wires in T012, but is independently testable via `RunWatcher.reattach` directly (T009's fake-adapter unit tests already cover this without US1's tool wiring). T022's lock placement is the single source of truth for `ThreadTurnLock` — no other task acquires it directly.
- **User Story 3 (Phase 5)**: Depends on Foundational (T005 `WorkspaceClient.cancel`, T004 store) and on US1's T015 (running-run banner) for T036's cancel button placement. Independently testable at the API layer — cancel of a run detached via a direct `RunWatcher.detach` call in tests, no dependency on US1/US2's tool-executor wiring.
- **User Story 4 (Phase 6)**: Depends on Foundational (T004 `list_in_progress`). Independently testable via the gate directly.
- **Polish (Phase 7)**: Depends on all four user stories.

### Within Each User Story

- Tests before the implementation task(s) they cover.
- Store/client/protocol changes before route/tool wiring that calls them.
- Backend before the corresponding `ze-web` slice.
- Locking (T022) before anything that relies on callers already being lock-aware (T023, T025).

### Parallel Opportunities

- Foundational: T003, T004, T005, T006 in parallel (different files); T007 waits on T003+T004+T006; T008/T009 in parallel once T006/T007 land.
- US1: T010/T011 in parallel; T017 (frontend tests) in parallel with backend tasks (different package).
- US2: T018–T021 in parallel; T022 must land before T023 and T025 (single-owner locking, see I1 remediation); T024 is independent of T022/T023.
- US3: T030/T031 in parallel; T036/T037 in parallel with backend tasks, and depend on US1's T015.
- US4: T038/T039 in parallel (different packages).
- Once Foundational is done, US1/US2/US3/US4 backend tracks can proceed in parallel if staffed — US2 and US4 both edit `gate.py`/`tools.py`/`container.py` at points, so a single-developer run should sequence US1 → US2 → US3 → US4 to avoid rework, per the Implementation Strategy below.

---

## Parallel Example: Foundational

```bash
Task: "Add follow_through_notified field to WorkspaceRun in core/ze-workspace/ze_workspace/types.py"
Task: "Add list_in_progress()/mark_follow_through_notified() to core/ze-workspace/ze_workspace/store.py"
Task: "Add WorkspaceClient.cancel() in core/ze-workspace/ze_workspace/client.py"
Task: "Implement ThreadTurnLock in core/ze-workspace/ze_workspace/turn_lock.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational.
3. Complete Phase 3: User Story 1 — wait-then-detach with no follow-up yet (a
   detached run just sits `ended_at IS NULL` until US2 lands; acceptable as an
   internal milestone, not a shippable increment on its own since SC-003 needs US2).
4. **STOP and VALIDATE**: quickstart.md Scenarios 1–2.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. US1 → wait-then-detach observable in chat and on the workspace page, but
   detached runs go silent (US2 not yet built) — keep behind the existing
   workspace-mode gate during this window.
3. US2 → follow-up turns + push land; this is the first fully shippable increment
   (US1 + US2 together satisfy every P1 story except cancel).
4. US3 → cancel; all P1 stories complete.
5. US4 → busy refusal messaging; P2 complete.
6. Polish.

### Suggested Sequencing for a Single Developer

Given the shared-file overlap noted above (`gate.py`, `tools.py`, `container.py`
each get touched by more than one story), implement in priority + dependency order:
Foundational → US1 → US2 → US3 → US4 → Polish, rather than parallelizing stories.
