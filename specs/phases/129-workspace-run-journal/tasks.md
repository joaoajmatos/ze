---

description: "Task list for Workspace Run Journal (Phase 129)"
---

# Tasks: Workspace Run Journal

**Input**: Design documents from `/specs/phases/129-workspace-run-journal/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md (all present)

**Tests**: Constitution Principle V (Test Discipline) is NON-NEGOTIABLE for this
repo — test tasks are included for every phase, not optional.

**Organization**: Tasks are grouped by user story (spec.md priorities) so each
can be implemented and validated independently, per the spec's own
Independent Test for each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 (P1), US2 (P2), US3 (P2), US4 (P2)

## Path Conventions

Two existing components, no new top-level directories:
- Sidecar: `sidecar/workspace/`
- Mind package: `core/ops/ze-workspace/ze_workspace/`
- Mind wiring: `apps/ze-api/ze_api/`

---

## Phase 1: Setup

**Purpose**: No new project/dependency initialization needed — both
`sidecar/workspace` and `core/ops/ze-workspace` already exist with their
current dependency sets (FastAPI/asyncio on the sidecar; httpx/asyncpg on the
mind). This phase only stands up the new sidecar test scaffold, which has none
today.

- [x] T001 Create `sidecar/workspace/tests/__init__.py` and
      `sidecar/workspace/tests/conftest.py` with a `TestClient(app)` fixture
      and a `tmp_path`-backed `WORKSPACE_ROOT` override (monkeypatch
      `supervisor.WORKSPACE_ROOT` and `main.WORKSPACE_ROOT` per test), matching
      the isolation style of `core/ops/ze-workspace/tests/conftest.py`.

**Checkpoint**: Sidecar tests are runnable (`cd sidecar/workspace && python -m
pytest tests/`) even though they collect zero tests yet.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The in-memory run journal and the sidecar/mind contract points
every user story builds on (data-model.md's `JournalEntry`/`JournalEvent`,
research.md Decisions 1–4 and 6). No user story task should start before this
phase is green.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T002 Add `JournalEntry` and `JournalEvent` dataclasses plus a
      `RunJournal` container (spawn/get/append-event/mark-terminal/evict) to
      `sidecar/workspace/supervisor.py`, replacing the bare `_current_proc`/
      `_lock` globals. Enforce the one-slot invariant (data-model.md: at most
      one `status == "running"` entry) and the 5-terminal-entry retention
      bound (research.md Decision 3).
- [x] T003 Rewrite `run_command` in `sidecar/workspace/supervisor.py` into
      `spawn_run(command, run_id, ...)`: creates the subprocess via
      `asyncio.create_subprocess_exec` as today, but returns as soon as the
      process is spawned (no `communicate()` wait); a background
      `asyncio.Task` reads `proc.stdout`/`proc.stderr` incrementally, appends
      redacted `JournalEvent`s (stdout/stderr) to the journal entry as they
      arrive, applies the existing `OUTPUT_PREVIEW_CHARS` truncation +
      spill-to-file logic at truncation time, and on exit/timeout computes
      `files_touched` via the existing `snapshot_tree`/`diff_snapshots` pair
      and appends the terminal `exit` event.
- [x] T004 Rewrite `POST /run` in `sidecar/workspace/main.py` per
      `contracts/sidecar-run-api.md`: accepts optional `id` in `RunBody`
      (generate one via `uuid4()` if absent), calls `supervisor.spawn_run`,
      returns `{"id": ...}` immediately (200), returns 409
      `{"error": "busy", "id", "command"}` if the one-slot invariant already
      holds.
- [x] T005 [P] Add `GET /runs/{id}` to `sidecar/workspace/main.py`: reads the
      journal entry, returns the status/exit_code/timed_out/previews/
      files_touched shape from `contracts/sidecar-run-api.md`; 404
      `{"error": "not_found"}` for an unknown/evicted id.
- [x] T006 [P] Add `GET /runs/{id}/events` to `sidecar/workspace/main.py`
      as a `StreamingResponse` of `application/x-ndjson`: replay buffered
      `JournalEvent`s in `seq` order, then continue yielding as new events are
      appended (support multiple concurrent readers on the same entry — Edge
      Case "both MAY read it"); close after the `exit` event; 404 for an
      unknown id before any bytes are sent.
- [x] T007 Add `POST /runs/{id}/cancel` to `sidecar/workspace/main.py` per
      `contracts/sidecar-run-api.md` (200/404/409 `already_terminal`); remove
      the old bare `POST /cancel` route. Update `reset_workspace` in
      `supervisor.py` to cancel by the currently-running entry's id
      internally (Phase 115 reset behavior unchanged from the caller's POV).
- [x] T008 [P] `sidecar/workspace/tests/test_journal.py`: cover spawn-returns-
      immediately, GET status while running vs. after exit, events replay-
      then-live and replay-only-after-exit, cancel (200/404/409), the
      one-slot 409 on `POST /run` while busy, and 6-entries-evicts-oldest
      retention (research.md Decision 3). Use real short subprocesses
      (`["sh", "-c", "sleep 0.05"]` / `["sh", "-c", "echo hi"]`), no mocking.
- [x] T009 Add migration `zws003_run_handle.py` to
      `core/ops/ze-workspace/ze_workspace/migrations/versions/`:
      `ALTER TABLE workspace_runs ADD COLUMN IF NOT EXISTS sidecar_dispatched
      BOOLEAN NOT NULL DEFAULT false` (revision `zws003`, `down_revision`/
      `depends_on` = `zws002`), with a symmetric `downgrade()`.
- [x] T010 [P] Add `sidecar_dispatched: bool = False` to the `WorkspaceRun`
      dataclass in `core/ops/ze-workspace/ze_workspace/types.py`; add a
      `JournalEventDTO` dataclass (`seq`, `type`, `data`, `exit_code`,
      `timed_out`) for the mind-side representation of a streamed event; add
      a `WorkspaceRunStatusDTO` dataclass mirroring `GET /runs/{id}`'s body.
- [x] T011 [US-shared] Update `_run_from_row`/`insert_in_progress_run`/
      `complete_run` (read + write of `sidecar_dispatched`) and the
      `WorkspaceStore` Protocol in
      `core/ops/ze-workspace/ze_workspace/store.py`; add
      `mark_sidecar_dispatched(run_id) -> bool` (same idempotent-UPDATE
      pattern as `mark_follow_through_notified`).
- [x] T012 Replace `WorkspaceClient.run()`/`cancel()` in
      `core/ops/ze-workspace/ze_workspace/client.py` with `start_run()`,
      `get_run()`, `watch_run()` (async generator over the ndjson stream via
      `httpx.AsyncClient.stream`), and `cancel_run(run_id)`, per
      `contracts/mind-workspace-api.md`. Update `_raise_for_status` mappings
      for the new 404 (`WorkspaceNotFoundError`) / 409 `already_terminal`
      (`WorkspaceRunAlreadyTerminalError`) bodies from T004/T007.
- [x] T013 [P] `core/ops/ze-workspace/tests/test_client.py`: extend for
      `start_run`/`get_run`/`watch_run`/`cancel_run` against a mocked
      `httpx` transport (existing test pattern), covering the same
      status-code mappings as T012.
- [x] T014 [P] `core/ops/ze-workspace/tests/test_store.py`: extend for
      `sidecar_dispatched` round-trip and `mark_sidecar_dispatched`
      idempotency.

**Checkpoint**: `POST /run` returns immediately with a real handle;
`GET /runs/{id}` and `GET /runs/{id}/events` are readable end-to-end; cancel
targets a handle. User story implementation can now begin.

---

## Phase 3: User Story 1 - A run survives the mind restarting (Priority: P1) 🎯 MVP

**Goal**: When `ze-api` restarts while a detached run is still going, the
eventual follow-up on that thread carries the real exit status, output
preview, and files touched — not a lost-output placeholder (FR-003, SC-001).

**Independent Test**: Start a command that outlives the short wait, restart
the mind while it is running, wait until it finishes, confirm the follow-up
on that conversation carries the real result (`quickstart.md` §1).

### Implementation for User Story 1

- [x] T015 [US1] Rework `_run_and_maybe_detach` in
      `core/ops/ze-workspace/ze_workspace/tools.py`: call
      `client.start_run(command, run_id=recorded.id, ...)`, then
      `store.mark_sidecar_dispatched(recorded.id)`; for the short-wait window,
      consume `client.watch_run(recorded.id)` up to `_short_wait_seconds`
      (via `asyncio.wait_for` around iterating the async generator until the
      `exit` event or the timeout) instead of awaiting a bare coroutine —
      replaces the current `asyncio.ensure_future(run_coro)`/
      `asyncio.wait_for(asyncio.shield(task), ...)` pattern, which no longer
      applies once the sidecar call itself returns immediately.
- [x] T016 [US1] Rework `RunWatcher` in
      `core/ops/ze-workspace/ze_workspace/followthrough.py`:
      - `detach(run)` (drop the `pending_completion` parameter — nothing to
        pass in anymore) starts a background task that iterates
        `client.watch_run(run.id)`, and on the `exit` event calls
        `store.complete_run(...)` with the real `exit_code`/
        `stdout_preview`/`stderr_preview`/`files_touched` read off that
        event and the entry's final `GET /runs/{id}` state, then `_dispatch`
        as today.
      - `reattach(run)`: if `run.sidecar_dispatched` is `False`, call
        `store.complete_run(run.id, status=FAILED, error_summary=...)`
        directly (sidecar never received this id — no call needed). Else call
        `client.get_run(run.id)`: `None` → mark failed with a plain-language
        `error_summary` ("the computer restarted and lost this run" per Edge
        Case 3); still running → resume via `detach()`; terminal → complete
        with the real result exactly as the `detach()` exit-event branch.
      - Delete `RunCompletionSource`, `SidecarPollCompletionSource`, and
        `_RECONCILE_UNAVAILABLE_PREVIEW` (research.md Decision 6).
- [x] T017 [US1] Update `build_workspace_stack` in
      `core/ops/ze-workspace/ze_workspace/bootstrap.py`: drop the
      `completion_source` parameter from `RunWatcher(...)` construction and
      from the function signature (no implementation left to inject).
- [x] T018 [P] [US1] `core/ops/ze-workspace/tests/test_followthrough.py`:
      extend/replace fixtures for the new `RunWatcher.detach`/`reattach`
      contract — cover (a) detach-then-exit-event completes with real data,
      (b) reattach with `sidecar_dispatched=False` marks failed without a
      sidecar call, (c) reattach with a still-running handle resumes
      watching and eventually dispatches follow-through exactly once, (d)
      reattach with a 404 (`get_run` returns `None`) marks failed in plain
      language, never fabricating success.
- [x] T019 [US1] Verify `reconcile_in_progress_workspace_runs` in
      `apps/ze-api/ze_api/compose.py` needs no signature change (it already
      calls `run_watcher.reattach(run)` per in-progress row); add/adjust a
      regression test in `apps/ze-api/tests/` asserting it is invoked for
      every `ended_at IS NULL` row at startup, per the existing pattern.
- [x] T020 [US1] Run `quickstart.md` §1 manually (or as an
      integration test using the sidecar `TestClient` + a fake `ze-api`
      restart by constructing a fresh `RunWatcher`/store pair mid-run) and
      confirm SC-001: 100% real exit + real preview, never the old
      placeholder string.

**Checkpoint**: User Story 1 is fully functional and independently testable —
a restart mid-run recovers the real result.

---

## Phase 4: User Story 2 - The user can watch a run that has let go (Priority: P2)

**Goal**: A detached run's live output is readable as it happens (stdout,
then stderr, then exit), not only as a final preview (FR-005, SC-002), without
displacing follow-through (FR-011).

**Independent Test**: Detach a long command that prints over time; confirm
new output appears before it exits; confirm the follow-up still fires exactly
once at terminal (`quickstart.md` §2).

### Implementation for User Story 2

- [x] T021 [US2] Add `GET /api/v0/workspace/runs/{id}/events` to
      `apps/ze-api/ze_api/api/routes/workspace.py`: proxies
      `client.watch_run(run_id)` as a `StreamingResponse` (reuse the ndjson
      framing from `contracts/sidecar-run-api.md` — this is a thin pass-
      through, not a re-encoding), 404 via the existing
      `WorkspaceNotFoundError` → `http_status_for` mapping.
- [x] T022 [P] [US2] `apps/ze-api/tests/` route test: connecting mid-run
      yields already-produced output before a synthetic delayed chunk, then
      the `exit` event; connecting after exit replays the full buffer
      immediately (Acceptance Scenario 2).
- [x] T023 [US2] Confirm (via `test_followthrough.py`, extending T018) that a
      client actively watching `/events` during a run does not suppress or
      duplicate the follow-up turn/completion push when the run becomes
      terminal — `RunWatcher._dispatch` is watcher-count-agnostic by
      construction (multiple `watch_run` readers vs. `RunWatcher`'s own
      internal watch are independent generator instances over the same
      journal entry), assert this explicitly with two concurrent watchers.

**Checkpoint**: User Stories 1 AND 2 both work independently — live output is
readable mid-run, and reattach after restart is unaffected by who else was
watching.

---

## Phase 5: User Story 3 - Stop the right run by its handle (Priority: P2)

**Goal**: Cancel targets a specific handle; a missing or already-terminal
handle kills nothing (FR-006, SC-003).

**Independent Test**: Start a detached run, cancel it by its handle, confirm
it stops and is reported cancelled; a subsequent new command can then start
(`quickstart.md` §3).

### Implementation for User Story 3

- [x] T024 [US3] Update `cancel_run` in
      `core/ops/ze-workspace/ze_workspace/rest.py` to call
      `client.cancel_run(run_id)` (T012's new method) instead of the old bare
      `client.cancel()`; keep the existing `WorkspaceNotFoundError`/
      `WorkspaceRunAlreadyTerminalError` → `run_watcher.cancel(run_id)` flow
      (unchanged shape, now backed by a real handle-targeted sidecar call).
- [x] T025 [US3] Update `execute_reset`/`resolve_reset` in
      `core/ops/ze-workspace/ze_workspace/rest.py`: `client.cancel()` calls
      become `client.cancel_run(<current in-progress run id from
      store.list_in_progress()>)` when one exists, else skipped (T007's
      sidecar-side reset already cancels its own current entry internally as
      a backstop).
- [x] T026 [P] [US3] `core/ops/ze-workspace/tests/test_client.py` /
      `test_sidecar_contract.py`: extend for `cancel_run` 200/404/409 against
      the new `/runs/{id}/cancel` route contract.
- [x] T027 [US3] Run `quickstart.md` §3 manually or as an integration test:
      cancel-in-progress (200, process actually stops within 15s — SC-003),
      cancel-already-terminal (409 "already finished"), cancel-unknown-id
      (404 "not running").

**Checkpoint**: All of US1–US3 independently functional — cancel is precise
by handle.

---

## Phase 6: User Story 4 - One command at a time, even after detach (Priority: P2)

**Goal**: While a detached run is in progress, a second workspace command or
skill script is refused, naming the running handle and command, for
conversation, user-initiated, and unattended origins alike (FR-007).

**Independent Test**: Leave a long run detached, ask for another command,
confirm the second does not start and the message names the running handle;
after it finishes/cancels, a new command may start (`quickstart.md` §4).

### Implementation for User Story 4

- [x] T028 [US4] In `workspace_run` and `workspace_run_skill_script`
      (`core/ops/ze-workspace/ze_workspace/tools.py`), call
      `_store.list_in_progress()` before any gate/sidecar call; if
      non-empty, return the FR-007 refusal text naming
      `running.command`/`running.id` from `contracts/mind-workspace-api.md`,
      without touching the sidecar (research.md Decision 5). Applies
      uniformly regardless of `WorkspaceRunOrigin` (conversation, user,
      unattended) since both tools share this one check.
- [x] T029 [P] [US4] `core/ops/ze-workspace/tests/test_tools.py`: extend for
      the new refusal — a fake `list_in_progress()` returning a row causes
      both `workspace_run` and `workspace_run_skill_script` to refuse without
      calling `client.start_run`, for all three `WorkspaceRunOrigin` values;
      confirm the refusal message contains the running run's id and command.
- [x] T030 [P] [US4] `sidecar/workspace/tests/test_journal.py`: assert the
      T004 one-slot 409 backstop still holds for a direct/manual `POST /run`
      call bypassing the mind's `list_in_progress()` check (defense in depth
      per data-model.md's one-slot invariant).
- [x] T031 [US4] Run `quickstart.md` §4 manually or as an integration test:
      second command refused with handle+command named; a new command starts
      once the first is terminal/cancelled.

**Checkpoint**: All four user stories independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Repo-wide consistency and Definition of Done per the
constitution's Development Workflow section.

- [x] T032 [P] Flip `specs/phases/129-workspace-run-journal/spec.md`'s
      `**Status**` header from `Draft` to `Implemented` once all tasks above
      are checked (Constitution I — status updated in the same commit as the
      implementation).
- [x] T033 [P] Update `specs/README.md`'s phase index row for 129 to point at
      this spec and mark it done, alongside the existing 115/116 rows.
- [x] T034 Run `make test-ze-workspace`, `make test-ze-api`, and
      `cd sidecar/workspace && python -m pytest tests/`; run `make lint`.
      All must pass (Constitution V, Definition of Done).
- [ ] T035 Walk through `quickstart.md` end-to-end once against a real (or
      locally-run) sidecar + `make dev` mind, not just the per-story
      integration tests, to catch any interaction between US1–US4 the
      per-story checkpoints missed.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup. BLOCKS all user stories —
  the journal, the four control-plane routes, and the mind-side
  client/store/type changes are shared by every story.
- **User Stories (Phase 3–6)**: All depend on Foundational completion.
  - US1 (P3) has no dependency on US2–US4.
  - US2 (P4) depends only on Foundational's `/runs/{id}/events` (T006) and
    `watch_run` (T012) — not on US1's `RunWatcher` rework, though T023
    exercises US1's watcher alongside US2's route for a joint regression
    check.
  - US3 (P5) depends only on Foundational's cancel route (T007) and
    `cancel_run` client method (T012).
  - US4 (P6) depends only on Foundational's `list_in_progress` (already
    existed pre-129) and the one-slot 409 (T004) — no dependency on US1–US3.
  - Recommended order remains priority order (P1 → P2 → P2 → P2) since US1 is
    the MVP and the spec explicitly calls it the hole everything else shares
    a contract with, but US2/US3/US4 could be staffed in parallel once
    Foundational is done.
- **Polish (Phase 7)**: Depends on all four user stories being complete.

### Within Each User Story

- US1: tools.py rework (T015) and RunWatcher rework (T016) can proceed in
  parallel (different files), both depend on Foundational; bootstrap.py
  (T017) depends on T016 (removes the parameter T016's deletion makes
  unused); tests (T018) depend on T015–T017; manual/integration validation
  (T020) depends on T018.
- US2: route (T021) depends only on Foundational; its test (T022) depends on
  T021; the joint watcher regression (T023) depends on both T021 and US1's
  T016.
- US3: rest.py updates (T024, T025) depend on Foundational's T012; tests
  (T026) depend on T024/T025; validation (T027) depends on T026.
- US4: tools.py refusal (T028) depends on Foundational only; its test (T029)
  and the sidecar backstop test (T030) depend on T028/T004 respectively;
  validation (T031) depends on T029/T030.

### Parallel Opportunities

- T005 and T006 (different routes, same file — coordinate to avoid a merge
  conflict, but logically independent) can be developed in parallel with
  T004 once T002/T003 land.
- T010, T013, T014 (mind-side types/tests, different files) can run in
  parallel with the sidecar-side T005–T008 once T002–T004 are stable enough
  to point a contract test at.
- Once Foundational is checkpointed: US1, US2, US3, US4 implementation tasks
  (T015/T016 vs. T021 vs. T024/T025 vs. T028) touch disjoint files and can
  proceed in parallel across developers.
- T032/T033 (docs) can run in parallel with T034 (test run).

---

## Parallel Example: Foundational Phase

```bash
# After T002-T004 (journal + POST /run) land, these can run together:
Task: "Add GET /runs/{id} to sidecar/workspace/main.py"                # T005
Task: "Add GET /runs/{id}/events to sidecar/workspace/main.py"         # T006
Task: "Add sidecar_dispatched + JournalEventDTO to ze_workspace/types.py"  # T010
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001)
2. Complete Phase 2: Foundational (T002–T014) — this is the bulk of the new
   contract surface; nothing in Phase 3 works without it
3. Complete Phase 3: User Story 1 (T015–T020)
4. **STOP and VALIDATE**: `quickstart.md` §1 — a restart mid-run recovers the
   real result (SC-001)
5. This alone closes the tolerated-loss gap the spec's Overview names as the
   primary motivation; US2–US4 are additive from here

### Incremental Delivery

1. Setup + Foundational → contract ready, nothing user-visible changes yet
2. US1 → restart-safety lands (MVP) → validate → deploy
3. US2 → live watching lands → validate → deploy
4. US3 → precise cancel lands → validate → deploy
5. US4 → the Phase 116 one-run-at-a-time gap closes → validate → deploy
6. Each story is additive; none breaks a previously-shipped one (all consume
   the same Foundational journal, none redefines its contract)

---

## Notes

- [P] tasks touch different files or, within `main.py`, logically
  independent route bodies — verify no merge conflict before parallelizing
  within one file.
- Every user story phase ends with a manual-or-integration run of its
  `quickstart.md` section — treat that as the phase's real Definition of
  Done, not just its unit tests passing.
- `SidecarPollCompletionSource` and the old blocking `run()`/bare `cancel()`
  client methods are deleted, not deprecated — no caller survives past T016/
  T012 in the same commit, so there is nothing to keep for back-compat
  (single-caller internal contract, per research.md Decision 1).
