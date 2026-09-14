# Implementation Plan: Workspace Run Journal

**Branch**: `129-workspace-run-journal` | **Date**: 2026-09-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/phases/129-workspace-run-journal/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

The workspace sidecar's `POST /run` today blocks the HTTP connection until the
subprocess exits (`supervisor.run_command` awaits `proc.communicate()`), and
`POST /cancel` targets whatever the single in-process `_current_proc` global
happens to be. When `ze-api` restarts mid-run, the connection that was awaiting
`/run` is gone, and Phase 116's `RunWatcher` falls back to polling `/stat`'s
`busy` flag and fabricating an "output unavailable" result — the tolerated loss
this phase closes.

This phase gives the sidecar an in-memory **run journal**: `POST /run` spawns
the subprocess as a background task, streams its stdout/stderr into a
per-handle event buffer, and returns `{id}` immediately. `GET /runs/{id}`,
`GET /runs/{id}/events`, and `POST /runs/{id}/cancel` let any caller — including
a `ze-api` process that just restarted — reattach to that handle, replay
buffered output, watch new output live, or stop it by identity. `ze-api`'s
`WorkspaceClient`/`RunWatcher`/`workspace_runs` schema are updated to carry the
sidecar's handle instead of assuming the original HTTP call is still alive, and
`workspace_run`/`workspace_run_skill_script` gain an explicit "already running"
refusal keyed off `WorkspaceStore.list_in_progress()` (closing Phase 116 User
Story 4). No new package, no new datastore, no change to isolation, modes, or
credentials handling — only the shape of the run contract between `ze-api` and
the always-on `ze-workspace` sidecar.

## Technical Context

**Language/Version**: Python 3.11 (both `ze-api` and the `sidecar/workspace`
FastAPI process)

**Primary Dependencies**: FastAPI + `asyncio.subprocess` (sidecar control API,
unchanged framework), `httpx` (mind-side `WorkspaceClient`, gains streaming
response support for `/runs/{id}/events`), `asyncpg` (mind-side
`workspace_runs` persistence, unchanged driver)

**Storage**: Postgres `workspace_runs` (existing table, one new nullable
column) on the mind side, N/A on the sidecar — the run journal is **in-process
memory only** (a bounded dict keyed by run id), matching Phase 115's decision
that the Fly volume is file truth and the sidecar carries no database of its
own. No SQLite, no VFS (explicitly out of scope, FR-009).

**Testing**: `pytest` via `make test-ze-workspace` (mind-side: client,
store, followthrough/RunWatcher, tools, turn_lock — existing suite extended)
and `make test-ze-api` for the REST route + container wiring. The
`sidecar/workspace` FastAPI app has no existing test suite (verified: no
`sidecar/workspace/**test**` files) — this phase adds one
(`sidecar/workspace/tests/test_journal.py`) using FastAPI's `TestClient`,
matching the pattern `sidecar/browser` would use if it had one. `asyncio_mode
= "auto"`, no real DB/LLM per Constitution V.

**Target Platform**: Two existing Fly.io deployments — `ze-workspace` sidecar
(`sidecar/workspace/fly.toml`, always-on, `min_machines_running = 1`) and
`ze-api` (Fly, FastAPI). No new deployment unit.

**Project Type**: Internal service-to-service contract change (backend only;
no `ze-web` UI in this phase — live output in chat is explicitly a later layer
on the same contract, per the spec's Input and Overview)

**Performance Goals**: SC-002 (a client watching a live run sees output
produced ≥5s before the command's own exit, for a command that prints
throughout its run — i.e. `/runs/{id}/events` must not buffer a whole run
before yielding anything); SC-003 (cancel of a named handle takes effect in
under 15s, unchanged budget from Phase 116's cancel-without-confirmation path)

**Constraints**: One run at a time remains a hard rule, not a queue (FR-007);
`POST /run` must return before the process exits (FR-001); shown output must
still pass Phase 115 `sanitize.redact()` (FR-012); the four pinned control-plane
paths (`POST /run`, `GET /runs/{id}`, `GET /runs/{id}/events`,
`POST /runs/{id}/cancel`) MUST exist verbatim; no Durable Objects, FUSE, SQLite-
as-filesystem, named egress, host-side git, or second execution backend
(FR-009, FR-010)

**Scale/Scope**: Single user, single workspace, single sidecar process, one
run in flight at a time — the run journal never holds more than one "running"
entry and a small bounded number of recently terminal ones (retention design
in `research.md`)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Spec-First Development**: Governed by spec 129, itself scoped under
  Phase 115/116. Status field will be flipped to `Planned` in this commit,
  `Implemented` at the end of `/speckit-implement`. PASS.
- **II. Single-User Model**: No `user_id`, no multi-tenant concept anywhere in
  this change — the run journal is process-global on the sidecar (one
  workspace, one user), matching every other Phase 115/116 primitive. PASS.
- **III. Layered Package Architecture**: All changes stay inside
  `core/ops/ze-workspace` (a `ZePlugin`-adjacent ops package, not core-with-
  domain-knowledge) and `sidecar/workspace` (an integration-style standalone
  process with no Ze domain imports — it already has none). `apps/ze-api` only
  gets wiring changes in `container.py`/`compose.py`, not new domain logic.
  No plugin gains a new `ze_core`/`ze_plugin` import. PASS.
- **IV. Typed, Explicit Python**: New types (`RunHandle`/journal event shapes)
  go in `ze_workspace/types.py` as dataclasses; sidecar-side journal entries
  are a plain dataclass too (no Pydantic beyond the existing FastAPI request
  bodies in `sidecar/workspace/main.py`, matching current style). Errors raise
  existing `WorkspaceError` subclasses (`WorkspaceNotFoundError` for an unknown
  handle, `WorkspaceRunAlreadyTerminalError` for cancel-after-finish — both
  already exist and need no new subclass). PASS.
- **V. Test Discipline**: New sidecar test suite mocks nothing external (it's a
  pure FastAPI app with subprocess calls — tests use real short-lived
  subprocesses like `sh -c "sleep 0.1"`, no network/DB). Mind-side tests mock
  `WorkspaceClient`/`asyncpg` per existing patterns. PASS.
- **VI. Explicit Persistence**: One new hand-written Alembic migration
  (`zws003`) on the existing `ze-workspace` `zws` chain, raw SQL, adding a
  nullable column — no ORM. PASS.
- **VII. One LLM Gateway, Local Embeddings**: Untouched — this phase has no
  LLM or embedding surface. PASS.

No violations. Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/phases/129-workspace-run-journal/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── sidecar-run-api.md    # POST /run, GET /runs/{id}, GET /runs/{id}/events, POST /runs/{id}/cancel
│   └── mind-workspace-api.md # WorkspaceClient + REST surface changes ze-api exposes
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
sidecar/workspace/
├── main.py                # FastAPI routes — /run, /runs/{id}, /runs/{id}/events,
│                           # /runs/{id}/cancel replace the blocking /run + bare /cancel
├── supervisor.py           # Gains RunJournal: dict[UUID, JournalEntry], spawn_run(),
│                           # stream_events(), cancel_handle(); loses _current_proc/_lock
│                           # as the sole run-identity primitive (kept as the "one slot"
│                           # guard, now keyed by id)
└── tests/
    └── test_journal.py     # New — start/reattach/watch/cancel/one-at-a-time

core/ops/ze-workspace/ze_workspace/
├── types.py                 # RunHandle-carrying fields on WorkspaceRun; journal event type
├── client.py                 # start_run()/get_run()/watch_run()/cancel_run(handle) replace
│                             # the old blocking run()/bare cancel()
├── followthrough.py          # RunWatcher.detach()/reattach() watch the sidecar handle via
│                             # the journal instead of polling /stat's busy flag;
│                             # SidecarPollCompletionSource deleted (no longer needed)
├── store.py                  # sidecar_run_id column read/write; list_in_progress() reused
│                             # for the FR-007 refusal (no store contract change)
├── tools.py                  # workspace_run/workspace_run_skill_script check
│                             # list_in_progress() before starting; refusal names the
│                             # running handle + command
├── rest.py                   # cancel_run/list_runs unchanged in shape, now backed by
│                             # real handle data instead of best-effort busy polling
└── migrations/versions/
    └── zws003_run_handle.py  # ADD COLUMN sidecar_run_id UUID NULL

apps/ze-api/ze_api/
├── container.py               # wiring unchanged in shape (same RunWatcher constructor)
└── compose.py                  # reconcile_in_progress_workspace_runs() unchanged call site;
                                 # behavior improves because RunWatcher.reattach() now
                                 # recovers real output instead of a placeholder
```

**Structure Decision**: No new packages, no new top-level directories. This is
a contract change inside the existing `sidecar/workspace` process and the
existing `core/ops/ze-workspace` package, consumed by `apps/ze-api` through the
same wiring points (`container.py`, `compose.py`) that Phase 115/116 already
established. `ze-web` is untouched — live streaming to chat is out of scope
here.

## Complexity Tracking

> Fill ONLY if Constitution Check has violations that must be justified

*No violations — table intentionally omitted.*
