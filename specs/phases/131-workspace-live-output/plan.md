# Implementation Plan: Workspace Live Output

**Branch**: `131-workspace-live-output` | **Date**: 2026-09-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/phases/131-workspace-live-output/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Stream the printed output of a detached, in-progress workspace run into the two
places it is already tracked but not yet shown — the chat still-running chip and the
`/workspace` in-progress banner — by having the frontend read the existing Phase 129
`GET /api/v0/workspace/runs/{id}/events` NDJSON stream directly (replay then live),
and closing a real redaction gap in that endpoint's per-event `data` field so shown
lines pass the same secret redaction the terminal preview already gets. No new
computer, no new backend event contract, no new persistence, no change to follow-through,
isolation, modes, or cancel rules.

## Technical Context

**Language/Version**: Python 3.11 (backend, `ze_api`/`ze_workspace`), TypeScript
(frontend, `ze-web`)

**Primary Dependencies**: FastAPI (`StreamingResponse`, already used by the amended
endpoint), React + `@tanstack/react-query` (existing `useWorkspaceRunsQuery` pattern),
browser `fetch` with a streaming response body reader (no new npm dependency)

**Storage**: N/A — no schema change; reuses `workspace_runs` (Phase 115) and the
sidecar run journal (Phase 129) unchanged

**Testing**: pytest (`make test-workspace`, `make test-ze-api`) for the redaction
amendment; vitest (`make test-web`) for the two new frontend hooks/components

**Target Platform**: Existing Ze deployment — FastAPI backend, browser SPA client

**Project Type**: web application (existing `apps/ze-api` + `apps/ze-web`)

**Performance Goals**: New lines visible within a few seconds of being printed (SC-001:
≥5s of visible lag margin before exit is the acceptance floor, not a target to hit
exactly); no additional polling load beyond one open streaming connection per
currently-rendered in-progress run (at most one, per the existing one-run busy rule)

**Constraints**: MUST NOT add a WebSocket frame type, a second REST endpoint, or any
persisted state (FR-007, FR-008); MUST NOT change isolation, modes, skill-script
approval, the busy rule, cancel confirmation, or the run contract; live preview text
MUST stay bounded by the existing Phase 129 emission cap, not a new one (research.md R2)

**Scale/Scope**: Single-user product (constitution II) — at most one in-progress
workspace run at a time (existing busy rule), so at most one open live-events stream
per surface (chat, workspace page) at any moment

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Spec-First Development**: Spec exists at `specs/phases/131-workspace-live-output/spec.md`,
  governed by Phase 129/116. PASS.
- **II. Single-User Model**: No `user_id`, no multi-tenant scoping added; the one-run
  busy rule already bounds this to a single viewer's single run. PASS.
- **III. Layered Package Architecture**: The redaction fix lives in `ze_api/api/routes/workspace.py`
  (composition root) calling `ze_workspace.sanitize.redact()` (already a core/ops
  package ze-api depends on) — no new cross-layer import, no plugin involved, no
  `ze_core`/`ze_plugin` touched. Frontend change stays within `entities/workspace`
  (query hooks) and existing `entities/message`/`widgets/workspace-management` UI,
  matching FSD layer order. PASS.
- **IV. Typed, Explicit Python**: No new Pydantic/dataclass types needed for the
  redaction amendment (reuses `JournalEventDTO`/existing dict line shape). If a typed
  DTO is introduced for the NDJSON line in `tasks.md`, it goes in `ze_workspace.types`
  as a dataclass, not a new Pydantic model outside `ze_api/api/schemas.py`. PASS
  (to be honored at task-writing time).
- **V. Test Discipline**: Plan requires a backend test asserting `/events` redacts a
  denylisted-key line (mocking `WorkspaceClient`/`RunStatusSource`, no real sidecar),
  and frontend tests for the new streaming hook using a mocked `fetch` reader (no real
  network). PASS (to be honored at task-writing time).
- **VI. Explicit Persistence**: No schema change, no migration. PASS.
- **VII. One LLM Gateway, Local Embeddings**: Not applicable — no LLM call in this
  feature. PASS.

No violations. Complexity Tracking section left empty.

## Project Structure

### Documentation (this feature)

```text
specs/phases/131-workspace-live-output/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/
│   └── workspace-run-events.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
apps/ze-api/ze_api/api/routes/workspace.py     # amend watch_workspace_run_events: redact() each stdout/stderr event.data

core/ops/ze-workspace/ze_workspace/sanitize.py # existing redact() — reused as-is, no change
core/ops/ze-workspace/tests/                   # new/extended test for the amended proxy behavior (or ze-api tests, wherever the proxy is tested today)

apps/ze-web/src/
├── entities/workspace/
│   ├── api/
│   │   └── useWorkspaceRunEventsQuery.ts      # NEW — streaming reader over GET /runs/{id}/events, exposes accumulated lines/status per data-model.md
│   └── index.ts                               # export the new hook
├── entities/message/ui/MessageBubble.tsx      # consume the new hook for the still-running chip's growing preview
└── widgets/workspace-management/ui/
    └── RunningRunBanner.tsx                   # consume the new hook per in-progress row
```

**Structure Decision**: Existing two-app web application layout
(`apps/ze-api` + `apps/ze-web`) is unchanged. All new code lands inside the existing
`ze_api`/`ze_workspace` packages and the existing `entities/workspace` FSD slice —
no new package, no new app, no new top-level directory.

## Complexity Tracking

*No Constitution Check violations — this section intentionally left empty.*
