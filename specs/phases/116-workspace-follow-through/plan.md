# Implementation Plan: Workspace Follow-Through

**Branch**: `116-workspace-follow-through` | **Date**: 2026-08-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/phases/116-workspace-follow-through/spec.md`

## Summary

Give the workspace computer from Phase 115 a Cursor-like exit from the turn: wait a
short time for a run to finish inline; if it hasn't, end the turn with "still running"
and keep the sidecar process going server-side under an `asyncio` watcher owned by
`ze-workspace`. When the watcher observes a `workspace_runs` row reach a terminal
status, it starts a normal follow-up turn on the originating conversation via the
existing `container.invoke_raw_turn` path (same mechanism WebSocket turns already
use), gated by a new per-thread turn lock so it never lands mid-reply. A completion
push through the existing `ProactiveNotifier` / `NativeAppInterface.push` fires only
when the WebSocket is not connected — reusing the connected-check that already gates
every other proactive push, not a new notification product. Cancel stops the sidecar
process and marks the run `cancelled`; the watcher treats that as terminal like any
other outcome. No new package: this lives inside `core/ze-workspace` (follow-through
orchestrator) and `apps/ze-api` (turn lock, wiring), extending Phase 115's
`workspace_runs` rows and REST surface rather than building a parallel model.

## Technical Context

**Language/Version**: Python 3.11+ (backend), matches Phase 115 and the existing
stack. No frontend framework change — extends the Phase 115 workspace page and
message chip.

**Primary Dependencies**: `ze-workspace` (Phase 115, extended here), `ze-agents`
(`RawInput`, `TurnResult`), `ze-core` (`container.invoke_raw_turn`,
`ze_core.conversation.turn`), `ze-proactive` (`ProactiveNotifier`), no new third-party
dependency. Reuses `NativeAppInterface`'s existing WebSocket-connected check
(`apps/ze-api/ze_api/interface/native.py`) rather than adding a second connectivity
signal.

**Storage**: PostgreSQL via asyncpg — extends Phase 115's `workspace_runs`
(`zws001`) in place; no new table for the run record itself (FR-012). One new
migration in `ze-workspace`'s existing chain adds only what a live in-progress run
needs beyond what 115 already modeled (see data-model.md — 115 already left
`ended_at` nullable and the row durable specifically for this spec). Watcher state
(which runs are being followed) is process memory, not a table — a startup
reconciliation pass re-adopts any `workspace_runs` row still without `ended_at`
so an `ze-api` restart doesn't strand a run without follow-through (same shape as
Phase 13's reminder startup replay).

**Testing**: pytest (`core/ze-workspace/tests/` for the watcher, turn-lock, and
cancel path with a fake `WorkspaceClient` and fake `Container`; `apps/ze-api/tests/`
for the REST cancel route and the `invoke_raw_turn` follow-up wiring). No real
Postgres, no real LLM, no real sidecar HTTP — same discipline as Phase 115.

**Target Platform**: Existing FastAPI service (`apps/ze-api`), no new deployable.

**Project Type**: Web application (existing monorepo layout) — this phase adds no
new project, only follow-through logic inside packages Phase 115 already places.

**Performance Goals**: SC-002 (turn ends and the user can send another message within
5s of the short wait elapsing); SC-005 (cancel takes effect in under 15s).

**Constraints**: Detach MUST NOT change workspace isolation, credentials handling,
network policy, or file storage (FR-012, FR-016) — those stay exactly as Phase 115
defined them. Follow-through MUST NOT invent a new async-conversation model (FR-003):
it is exactly one more `invoke_raw_turn` call plus the existing push path. One run at
a time remains a hard gate (FR-011, FR-015) — the busy check Phase 115 already has in
`WorkspaceGate`/`WorkspaceStore` now must also see runs that are in-progress after
their originating turn ended, not just runs mid-turn.

**Scale/Scope**: Single workspace, single in-flight run, single follow-up watcher.
Short wait is a low tens-of-seconds constant; existing 120s run budget (Phase 115)
is unchanged and still the outer bound after detach (FR-014).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Spec-First Development** — PASS. Follows
  `specs/phases/116-workspace-follow-through/spec.md`, attaches to Phase 115's spec
  without re-deciding it.
- **II. Single-User Model** — PASS. One workspace, one run at a time, no `user_id` /
  tenancy; the turn lock is keyed by `thread_id`, not by user.
- **III. Layered Package Architecture** — PASS. Follow-through orchestration
  (watcher, cancel, terminal-status → follow-up dispatch) lives in `core/ze-workspace`,
  a `core/` package with no domain knowledge, wired by `apps/ze-api` exactly like
  Phase 115. The watcher calls `container.invoke_raw_turn` and
  `ProactiveNotifier`/`AppInterface.push` through injected protocols passed at
  construction — `ze-workspace` does not import `ze_core` or `ze_api` types
  directly; it depends on small Protocols in `ze_workspace/followthrough.py`
  (`TurnStarter`, `PushSender`) that `apps/ze-api` satisfies with the real
  container/interface at wiring time, the same DI shape `ze-workspace` already
  uses for `WorkspaceClient`. Plugins are untouched — no plugin imports anything
  new here.
- **IV. Typed, Explicit Python** — PASS. New dataclasses/`StrEnum` values (if any)
  in `ze_workspace/types.py`; typed `ZeError` subclasses for cancel-on-already-
  terminal; async watcher, no blocking waits; constructor injection for the
  `TurnStarter`/`PushSender` Protocols.
- **V. Test Discipline** — PASS (planned). Tests in `core/ze-workspace/tests/`
  (watcher terminal-transition, turn-lock ordering, cancel-already-finished),
  `apps/ze-api/tests/` (REST cancel, `invoke_raw_turn` follow-up call), `ze-web`
  vitest for the "still running" chip and cancel button. Mocked `WorkspaceClient`,
  mocked `Container`/`AppInterface`, no real DB or LLM.
- **VI. Explicit Persistence** — PASS. Any new column lives on `ze-workspace`'s
  existing `zws` chain (next revision after Phase 115's `zws001`), raw SQL, no ORM.
- **VII. One LLM Gateway, Local Embeddings** — PASS. Follow-up turns go through the
  existing graph/`OpenRouterClient` path unchanged; no new model call shape.

No violations requiring Complexity Tracking justification.

**Post-Phase-1 re-check**: still no per-user columns, no ORM, no core enum of plugin
identities, no new notification product (push reuses `ProactiveNotifier`). The
`TurnStarter`/`PushSender` Protocol boundary keeps `ze-workspace` free of `ze_core`/
`ze_api` imports even though it now needs to start turns and push — confirmed against
`core/ze-workspace`'s existing DI pattern for `WorkspaceClient`. Gate still PASSES
after design.

## Project Structure

### Documentation (this feature)

```text
specs/phases/116-workspace-follow-through/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md         # Phase 1
├── quickstart.md         # Phase 1
├── contracts/
│   └── workspace-followthrough-api.md   # REST additions + internal orchestrator contract
└── tasks.md              # Phase 2 (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
core/ze-workspace/ze_workspace/
├── types.py                           # + WorkspaceRunOutcome helpers (no new run status;
│                                       #   detach adds no new enum member — see data-model)
├── followthrough.py                   # NEW — RunWatcher: waits short_wait, hands run to a
│                                       #   background asyncio.Task; on terminal status, waits
│                                       #   for the ThreadTurnLock then calls TurnStarter;
│                                       #   sends via PushSender only if the caller reports
│                                       #   disconnected. Protocols: TurnStarter, PushSender.
├── turn_lock.py                       # NEW — ThreadTurnLock: asyncio.Lock per thread_id,
│                                       #   acquired by the API layer around every turn
│                                       #   (invoke_raw_turn/resume_turn) and by the watcher
│                                       #   before starting a follow-up.
├── gate.py                            # busy check extended to see in-progress (no ended_at)
│                                       #   runs, not just mid-turn ones
├── store.py                           # + reconciliation query: runs with ended_at IS NULL
│                                       #   at startup (re-adopt for the watcher)
├── client.py                          # + cancel() call to sidecar /cancel (Phase 115 shape)
├── rest.py                            # + cancel dict facade
└── migrations/versions/
    └── zws002_run_followthrough.py    # only if data-model.md finds a needed column;
                                        #   otherwise this phase adds no migration

apps/ze-api/ze_api/
├── container.py                       # ThreadTurnLock instance; wraps invoke_raw_turn /
│                                       #   resume_turn acquisition; TurnStarter/PushSender
│                                       #   adapters passed into the ze-workspace RunWatcher
│                                       #   at bootstrap
├── compose.py                         # RunWatcher startup reconciliation (like proactive
│                                       #   job registration fan-out)
├── api/routes/workspace.py            # + POST /workspace/runs/{id}/cancel
├── api/schemas.py                     # + WorkspaceRunCancelResponse
└── api/websocket/turns.py             # unchanged call shape; turn lock wraps it

apps/ze-web/src/
├── entities/workspace/                # + "still running" run state, cancel mutation
├── widgets/workspace-management/      # + running-run banner, cancel button
└── entities/message/ui/MessageBubble.tsx  # "still running" chip on the detaching turn

core/ze-workspace/tests/
apps/ze-api/tests/
apps/ze-web/src/**/*.test.ts(x)
```

**Structure Decision**: No new package or sidecar. Follow-through is new modules
inside `core/ze-workspace` (`followthrough.py`, `turn_lock.py`) wired by
`apps/ze-api`, mirroring how Phase 115 already wires `WorkspaceGate`/`WorkspaceClient`
through `container.py` and `compose.py`. The turn lock lives in `ze-workspace` (it is
workspace follow-through's own requirement) but is applied by `apps/ze-api` around
every turn entry point, not only workspace-triggered ones, so User Story 2's "does
not interrupt mid-reply" holds for any turn on that thread, not just workspace turns.

## Complexity Tracking

*No Constitution Check violations — this section is empty.*
