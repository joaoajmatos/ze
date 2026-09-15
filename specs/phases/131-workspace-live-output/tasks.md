---

description: "Task list for Workspace Live Output (Phase 131)"

---

# Tasks: Workspace Live Output

**Input**: Design documents from `/specs/phases/131-workspace-live-output/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/workspace-run-events.md, quickstart.md

**Tests**: Included — constitution Principle V (Test Discipline) is non-negotiable.

**Organization**: Tasks are grouped by user story (US1 = P1 chat live output, US2 = P2 workspace-page live output) per spec.md.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2)

## Path Conventions

Existing web application layout: `apps/ze-api/ze_api/...` (backend), `apps/ze-web/src/...` (frontend), `core/ops/ze-workspace/...` (workspace package). See plan.md's Project Structure for the exact files touched.

---

## Phase 1: Setup

*No setup tasks.* This feature adds no new dependency, package, migration, or scaffolding — it amends one existing endpoint and adds one new query hook inside the existing `entities/workspace` slice (research.md, plan.md Project Structure).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The redacted event stream and the shared streaming hook are consumed by both User Story 1 (chat) and User Story 2 (workspace page). Neither story can be correctly implemented before these exist.

**⚠️ CRITICAL**: Complete this phase before starting either user story.

- [X] T001 [P] Redact `stdout`/`stderr` event `data` in `watch_workspace_run_events` using `ze_workspace.sanitize.redact()` before yielding each NDJSON line, in `apps/ze-api/ze_api/api/routes/workspace.py` (FR-006, research.md R3, contracts/workspace-run-events.md). Leave `exit` lines untouched (no free-text `data` to redact).
- [X] T002 [P] Add a test asserting a denylisted-key line (e.g. `OPENROUTER_API_KEY=sk-or-...`) streamed through `/api/v0/workspace/runs/{id}/events` comes back as `[redacted]`, in `apps/ze-api/tests/api/test_workspace_events.py` (extend the existing file; mock the run-events source the way the file's existing tests already do — no real sidecar).
- [X] T003 [P] Create `useWorkspaceRunEventsQuery(runId: string | null)` in `apps/ze-web/src/entities/workspace/api/useWorkspaceRunEventsQuery.ts`: opens a streaming `fetch` to `GET /api/v0/workspace/runs/{runId}/events`, reads the response body incrementally, parses newline-delimited JSON lines (`{seq, type, data, exit_code?, timed_out?}`), and exposes the accumulated state shape from data-model.md (`lines`, `lastSeq`, `status`, `exitCode`, `looksBinary`). Returns `status: "unavailable"` and stops (no invented output) if the fetch fails or the stream ends without an `exit` event (FR-010). Does nothing when `runId` is `null`.
- [X] T004 [P] Export the new hook from `apps/ze-web/src/entities/workspace/index.ts`.
- [X] T005 [US1][US2 shared, P] Add a test for `useWorkspaceRunEventsQuery` covering: replay-then-continue ordering by `seq`, no duplicate prefix on a second mount for the same `runId` (FR-002, edge case in spec.md), transition to `status: "closed"` on the `exit` line, and `status: "unavailable"` when the stream errors before `exit` (FR-010), in `apps/ze-web/src/entities/workspace/api/useWorkspaceRunEventsQuery.test.ts` (mock the streaming `fetch` response — no real network).

**Checkpoint**: Redacted event stream and shared hook exist and are tested. Both user stories can now proceed.

---

## Phase 3: User Story 1 - See what a detached command is printing in the conversation (Priority: P1) 🎯 MVP

**Goal**: The chat still-running chip grows with the command's printed output while it runs, and replays already-produced lines when the conversation is (re)opened mid-run, without touching follow-through.

**Independent Test**: Detach a command that prints several lines over time, stay on the conversation, confirm new output appears before the command exits, then confirm the follow-up still fires exactly once (spec.md User Story 1 Independent Test).

### Tests for User Story 1

- [X] T006 [P] [US1] Add a test asserting the trace-building function in `core/engine/ze-core/ze_core/orchestration/nodes/trace.py` extracts the run id out of a `"[still running] run <uuid>: ..."` tool result and sets `run_entry["id"]`, in `core/engine/ze-core/tests/orchestration/nodes/test_trace_workspace.py` (extended the existing dedicated file rather than creating a new one).
- [X] T007 [P] [US1] Extend `MessageBubble.test.tsx` (`apps/ze-web/src/entities/message/ui/MessageBubble.test.tsx`) to cover: the still-running chip renders growing text from `useWorkspaceRunEventsQuery` when `workspace.runs[].id` is present and `status === "in_progress"`, renders without live text (falls back to today's static chip) if `id` is absent, and stops updating once the hook reports `status: "closed"`.

### Implementation for User Story 1

- [X] T008 [US1] In `core/engine/ze-core/ze_core/orchestration/nodes/trace.py`, parse the run id out of the `"[still running] run {id}: ..."` result string (the tool already embeds it — `core/ops/ze-workspace/ze_workspace/tools.py:262`) and add it as `run_entry["id"]` next to the existing `status: "in_progress"` assignment. Non-still-running (terminal) entries do not need an id added here (T008 is scoped to what US1 needs; terminal previews are shown by the existing follow-up message, not this phase).
- [X] T009 [US1] Add `id?: string` to the `runs` array element type on `WorkspaceChipTrace` in `apps/ze-web/src/entities/message/ui/MessageBubble.tsx`.
- [X] T010 [US1] In `MessageBubble.tsx`, call `useWorkspaceRunEventsQuery(stillRunning?.id ?? null)` and render its accumulated `lines` (redacted, per T001) under the existing `data-testid="workspace-still-running-chip"` chip as a small growing `<pre>`-style preview, truncated by the hook's inherited server-side cap (no new client cap, research.md R2). Show a short "output is not printable" note instead of raw text when `looksBinary` is true (research.md R4). Do not change the chip's existing text/label or the `workspace-chip` (non-running) branch.
- [X] T011 [US1] Confirm no change was made to `apps/ze-api/ze_api/interface/native.py`, the `RunWatcher`/follow-through path, or the `trace_update` WS frame cadence — this story only adds a client-side read of the existing `/events` stream (FR-004, FR-008). (Verification task — no new file; check via `git diff` before marking complete.)

**Checkpoint**: User Story 1 is fully functional and independently testable per quickstart.md Scenario A. This is the MVP slice.

---

## Phase 4: User Story 2 - See the same unfolding output on the workspace page (Priority: P2)

**Goal**: The `/workspace` in-progress banner shows the same growing preview as the conversation for the same run, and stopping the run from there halts preview growth.

**Independent Test**: Start a detached printing command, open `/workspace` while it runs, confirm unfolding output, cancel or wait for completion, confirm the preview matched what chat showed (spec.md User Story 2 Independent Test).

### Tests for User Story 2

- [X] T012 [P] [US2] Extend `apps/ze-web/src/widgets/workspace-management/ui/RunningRunBanner.test.tsx` to cover: an in-progress row renders growing live text sourced from `useWorkspaceRunEventsQuery(run.id)`, the preview stops updating once "Stop" is clicked and cancel succeeds, and a `looksBinary` run shows the same not-printable note as chat (FR-003, FR-009).

### Implementation for User Story 2

- [X] T013 [US2] In `apps/ze-web/src/widgets/workspace-management/ui/RunningRunBanner.tsx`, for each `inProgress` row call `useWorkspaceRunEventsQuery(run.id)` and render its `lines` (or the not-printable note) under that row's existing status text, matching the presentation used in `MessageBubble.tsx` (T010) so the two surfaces read as one truth (FR-003).
- [X] T014 [US2] Confirm the existing `cancelRun` mutation flow in `RunningRunBanner.tsx` is unchanged (still `POST /runs/{id}/cancel`, no second confirmation) and that once cancel succeeds the row's live preview stops growing — this follows automatically if the row disappears from `inProgress` (i.e. `useWorkspaceRunsQuery` refetch removes it) once `ended_at` is set, per FR-009. (Verification task — no new cancel logic; check via the existing test in T012.)

**Checkpoint**: User Stories 1 AND 2 both work independently and consistently per quickstart.md Scenarios A and B.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Final validation against the spec's success criteria and non-goals.

- [ ] T015 [P] Run quickstart.md Scenario C (redaction) end-to-end against a local `make dev-full` + workspace sidecar, confirming both chat and `/workspace` show `[redacted]` for a denylisted-key line (SC-004).
- [ ] T016 [P] Run quickstart.md Scenario D (stream unavailable) — stop the sidecar mid-run and confirm the still-running indicator stays honest with no invented output in either surface (FR-010).
- [X] T017 Update `specs/phases/131-workspace-live-output/spec.md` **Status** field from `Draft` to `Implemented` and update `specs/README.md`'s index row for phase 131, in the same commit as the implementation (constitution Principle I).
- [X] T018 `make test-ze-api && make test-web && make lint` — full local verification before calling the phase done.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: None — skipped, no tasks.
- **Foundational (Phase 2)**: No dependencies beyond existing code — BLOCKS both user stories (T001–T005 must land first: US1/US2 both read the redacted stream via the shared hook).
- **User Story 1 (Phase 3)**: Depends on Phase 2. No dependency on User Story 2.
- **User Story 2 (Phase 4)**: Depends on Phase 2. Reuses the same hook and the same rendering approach as US1 (T013 references T010's pattern) but does not require US1's code to exist first — the dependency is conceptual (consistency of presentation), not a build order.
- **Polish (Phase 5)**: Depends on both user stories being complete.

### Parallel Opportunities

- T001, T002, T003, T004 can all run in parallel (different files: backend route, backend test, new hook, index export). T005 depends on T003/T004 existing.
- T006 and T007 can run in parallel (different packages/files).
- T015 and T016 can run in parallel (independent manual verification scenarios).

---

## Parallel Example: Foundational Phase

```bash
Task: "Redact stdout/stderr event data in apps/ze-api/ze_api/api/routes/workspace.py"
Task: "Add redaction test in apps/ze-api/tests/api/test_workspace_events.py"
Task: "Create useWorkspaceRunEventsQuery in apps/ze-web/src/entities/workspace/api/useWorkspaceRunEventsQuery.ts"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 2: Foundational (redaction fix + shared hook).
2. Complete Phase 3: User Story 1 (chat live output).
3. **STOP and VALIDATE**: Run quickstart.md Scenario A.
4. This alone satisfies the spec's stated priority (P1) and is demoable.

### Incremental Delivery

1. Foundational → chat live output (US1, MVP) → workspace-page live output (US2) → Polish (redaction/unavailable verification, spec status update).

## Notes

- No task in this list adds a WebSocket frame type, a second REST endpoint, a database migration, or changes isolation/modes/cancel-confirmation/follow-through cadence — matching FR-007/FR-008 and the plan's Constitution Check.
- T008 is the one genuine "missing plumbing" fix this phase depends on: the run id already exists in the tool's reply text (`ze_workspace/tools.py:262`) but was never parsed into the trace the chat chip reads from.
