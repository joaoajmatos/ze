# Implementation Plan: Web UI HIG Audit Fixes

**Branch**: `117-web-hig-fixes` | **Date**: 2026-08-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/phases/117-web-hig-fixes/spec.md`

## Summary

> **Amended 2026-10-08** after a re-audit (see spec.md Clarifications). The original
> "13 issues, ze-web only, no backend" framing is superseded. US3, US6, US11 and the
> FR-014 part of US10 are already done. US8 is deferred. US9 is split into a future
> phase except for a static AI-disclosure line. US1 now has a traced root cause that
> includes **backend** defects, so this phase has two independently testable blocks.

**[WEB] block** (`apps/ze-web`, FSD): US1 client recovery (bounded watchdog, history
check, visible retry, clear thinking on socket close, no blanket clear on reconnect,
`thread_id` on the ephemeral send); US2+US7 `md` click flyout with accessible names;
US4 launcher spacing; US5 route-derived panel label; US10 mobile label size and
back-button target; US3 desktop X nit; US9 static AI-disclosure line.

**[BE] block** (`apps/ze-api`, independent of the web block; picked up after phase 163):
1. One failed send must not null the shared socket. `ConnectionManager.push` and
   `send_frame` set `self._ws = None` on any exception (`connection.py:123-138`) even
   though the socket may still be open. The reply is stored (`native.py:103`) but later
   pushes silently no-op. Confirmed mechanism; the trigger (for example a trace that
   fails JSON serialization in `native.py:115-122`) is suspected.
2. Send a terminal frame when a turn yields no response (`turns.py:122` has no `else`).
3. Tag `error` frames with `thread_id` (`endpoint.py:199-203` "thread_id required").

Web recovery (watchdog plus history check) guarantees US1 regardless of which backend
path fails, so the web block can ship before the backend block.

## Technical Context

**Language/Version**: TypeScript 5.x, React 18, Vite 6 (existing `apps/ze-web` stack — no new language/framework)

**Primary Dependencies**: React Router, TanStack Query, Zustand (`useWsStore`, `useSession`, `useOverlayStore`), Tailwind CSS v4 (`@theme` tokens in `globals.css`), framer-motion (`ContextOverlay`), `@myguyze/ze-client` (typed WS/REST SDK) — all already in use, no new dependencies anticipated

**Storage**: N/A — no schema or persistence changes. The [BE] block touches `apps/ze-api/ze_api/api/websocket/{connection,endpoint,turns}.py` and `ze_api/interface/native.py`; no migrations.

**Testing**: Vitest + React Testing Library (`src/**/*.test.ts(x)`), existing pattern (see `ConfirmBar.test.tsx`, `MessageBubble.test.tsx`, `session-store.test.ts` for the closest analogues to the components touched here). `make test-web`.

**Target Platform**: Browser (responsive web SPA) — mobile (~390px), tablet/medium desktop (~768–1023px, the `md` Tailwind breakpoint), and wide desktop (≥1024px, `lg`) all in scope, since the audit findings span all three.

**Project Type**: Web application (existing FSD frontend + FastAPI backend monorepo) — this feature touches only the `apps/ze-web` side of that split.

**Performance Goals**: No new performance targets; existing WS/render performance must not regress. The stuck-loading fix (User Story 1) should resolve within the same time budget replies already take today (no slower perceived latency).

**Constraints**: `WsErrorFrame` already declares optional `thread_id` (`apps/ze-api/ze_api/api/schemas.py:686`), so tagging error frames needs no schema or `@myguyze/ze-client` change; the server just has to populate it. Must not change the WS message contract's external shape (`@myguyze/ze-client` types) unless User Story 1's root cause requires it — if so, treat that as a deliberate, called-out exception, not a silent change. Must preserve existing dark-only visual theme (out of scope per audit — not itself a finding this feature addresses).

**Scale/Scope**: (amended) 7 in-scope stories; 4 already done, 1 deferred, 1 split out. Originally 10 user stories / 13 findings across 4 areas of one frontend app (`AppShell`/`NavGroup` navigation, `ContextOverlay`, `SettingsWorkspace`, `useChatWorkspace`/`MessageBubble` chat loop). No multi-user or scale dimension — Ze is single-user (Constitution Principle II).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Applies? | Assessment |
|---|---|---|
| I. Spec-First Development | Yes | Spec exists at `specs/phases/117-web-hig-fixes/spec.md`, status will move to `implemented` in the same commit as the code per this principle. |
| II. Single-User Model | Yes | No user-scoping introduced; all fixes are UI/interaction-level. Pass. |
| III. Layered Package Architecture | No | This feature is entirely within `apps/ze-web` (a leaf app, not a `core`/`plugin`/`integration` package) — the layering rule doesn't apply here beyond ze-web's own internal FSD layer order (`pages → widgets → features → entities → shared`), which every fix below respects (no new cross-layer violations introduced). |
| IV. Typed, Explicit Python | Yes ([BE] block) | Touched `ze_api` code follows typed errors and `get_logger`. Narrow the broad `except Exception` in socket send paths where practical. |
| V. Test Discipline (NON-NEGOTIABLE) | Yes | Every user story below ships with a Vitest test per FSD slice touched, following the existing `ConfirmBar.test.tsx`/`session-store.test.ts` patterns. `make test-web` and `make lint` must pass before any story is considered done. |
| VI. Explicit Persistence | No | No schema changes. |
| VII. One LLM Gateway, Local Embeddings | No | Not touched. |

**Gate result**: PASS. No violations requiring justification in Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/phases/117-web-hig-fixes/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
└── tasks.md              # Phase 2 output (/speckit-tasks — not created by this command)
```

No `contracts/` directory: this feature adds no new REST/WS contract surface.
User Story 1 may touch the *delivery* of the existing `message` WS frame type,
but the frame's shape (already defined in `@myguyze/ze-client`) is not
expected to change — see Research, Unknown 1, for the fallback path if it
does.

### Source Code (repository root)

All changes are inside `apps/ze-web/src/`, following its existing
Feature-Sliced Design layout (`pages → widgets → features → entities →
shared`). No new top-level slices are introduced — every fix lands in a file
that already exists in one of these areas:

```text
apps/ze-web/src/
├── widgets/
│   ├── app-shell/ui/
│   │   ├── AppShell.tsx           # US2 (nav reachability), US10 (mobile label size)
│   │   ├── NavGroup.tsx           # US2 (md-width reachability), US7 (accessible names)
│   │   └── ContextOverlay.tsx     # US3, US4, US5 (dismiss, collision, mislabeling)
│   ├── settings-workspace/ui/
│   │   └── SettingsWorkspace.tsx  # US6 (wide-window layout)
│   └── chat-workspace/model/
│       └── useChatWorkspace.ts    # US1 (stuck loading)
├── entities/
│   ├── message/ui/
│   │   ├── ChatInput.tsx          # US9 (static AI-disclosure line only; feedback/retry split out)
│   │   └── ChatMessageList.tsx    # US1 (delivery-failed retry row)
│   └── session/model/
│       └── session-store.ts       # US1 (only if root cause is thread_id related)
├── shared/
│   ├── config/
│   │   └── nav-routes.ts          # US5 (getRouteLabel shared with TopBar); US8 deferred
│   ├── ui/layout/
│   │   └── TopBar.tsx             # US10 (back-button tap target)
│   └── api/                       # US1 (WS frame handling, if client-side fix)
└── pages/
    ├── workflows/, goals/          # US10 (humanized workflow/goal titles — display only)
```

Backend ([BE] block, confirmed in scope):

```text
apps/ze-api/ze_api/api/websocket/connection.py, endpoint.py, turns.py
apps/ze-api/ze_api/interface/native.py
apps/ze-api/tests/api/ (new WS delivery tests)
```

**Structure Decision**: Single existing web app (`apps/ze-web`), FSD layout
already in place — no new project, package, or top-level directory is
created by this feature. This matches "Option 2: Web application" from the
template, scoped to only the `frontend/` (here, `apps/ze-web`) side, since no
new backend contract is being added.

## Complexity Tracking

*No entries — Constitution Check passed with no violations.*
