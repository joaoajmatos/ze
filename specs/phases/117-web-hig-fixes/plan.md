# Implementation Plan: Web UI HIG Audit Fixes

**Branch**: `117-web-hig-fixes` | **Date**: 2026-08-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/phases/117-web-hig-fixes/spec.md`

## Summary

Fix 13 UI/UX and correctness issues found in a live Apple-HIG-grounded audit of
`apps/ze-web`, confirmed by resizing the running app across mobile/tablet/desktop
widths and by reproducing a stuck-chat-loading bug end-to-end against a live
backend. Three are correctness bugs (chat replies that never render, a
navigation dead-zone at tablet width, an unreliable contextual-panel
open/dismiss interaction); the rest are accessibility, layout-adaptability, and
content-polish gaps. All work is scoped to `apps/ze-web` (React/TypeScript,
Feature-Sliced Design); no new backend endpoints or schema changes are
expected — User Story 1 may require a backend-side root-cause check of the
WebSocket delivery path, but the fix itself is expected to land client-side
(see Research, Unknown 1).

## Technical Context

**Language/Version**: TypeScript 5.x, React 18, Vite 6 (existing `apps/ze-web` stack — no new language/framework)

**Primary Dependencies**: React Router, TanStack Query, Zustand (`useWsStore`, `useSession`, `useOverlayStore`), Tailwind CSS v4 (`@theme` tokens in `globals.css`), framer-motion (`ContextOverlay`), `@myguyze/ze-client` (typed WS/REST SDK) — all already in use, no new dependencies anticipated

**Storage**: N/A — no schema or persistence changes; all fixes are client-side rendering/interaction/layout logic. User Story 1 may touch `ze_api/interface/native.py` (WS frame delivery) if the root cause turns out to be server-side, but no data model changes either way.

**Testing**: Vitest + React Testing Library (`src/**/*.test.ts(x)`), existing pattern (see `ConfirmBar.test.tsx`, `MessageBubble.test.tsx`, `session-store.test.ts` for the closest analogues to the components touched here). `make test-web`.

**Target Platform**: Browser (responsive web SPA) — mobile (~390px), tablet/medium desktop (~768–1023px, the `md` Tailwind breakpoint), and wide desktop (≥1024px, `lg`) all in scope, since the audit findings span all three.

**Project Type**: Web application (existing FSD frontend + FastAPI backend monorepo) — this feature touches only the `apps/ze-web` side of that split.

**Performance Goals**: No new performance targets; existing WS/render performance must not regress. The stuck-loading fix (User Story 1) should resolve within the same time budget replies already take today (no slower perceived latency).

**Constraints**: Must not change the WS message contract's external shape (`@myguyze/ze-client` types) unless User Story 1's root cause requires it — if so, treat that as a deliberate, called-out exception, not a silent change. Must preserve existing dark-only visual theme (out of scope per audit — not itself a finding this feature addresses).

**Scale/Scope**: 10 user stories / 13 findings across 4 areas of one frontend app (`AppShell`/`NavGroup` navigation, `ContextOverlay`, `SettingsWorkspace`, `useChatWorkspace`/`MessageBubble` chat loop). No multi-user or scale dimension — Ze is single-user (Constitution Principle II).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Applies? | Assessment |
|---|---|---|
| I. Spec-First Development | Yes | Spec exists at `specs/phases/117-web-hig-fixes/spec.md`, status will move to `implemented` in the same commit as the code per this principle. |
| II. Single-User Model | Yes | No user-scoping introduced; all fixes are UI/interaction-level. Pass. |
| III. Layered Package Architecture | No | This feature is entirely within `apps/ze-web` (a leaf app, not a `core`/`plugin`/`integration` package) — the layering rule doesn't apply here beyond ze-web's own internal FSD layer order (`pages → widgets → features → entities → shared`), which every fix below respects (no new cross-layer violations introduced). |
| IV. Typed, Explicit Python | No | No Python changes expected. If User Story 1's root cause is server-side, any touched code in `ze_api`/`ze_core` must still follow this principle (typed errors, no bare `Exception`, `get_logger`). |
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
│   │   ├── MessageBubble.tsx      # US9 (feedback/retry affordance)
│   │   └── ChatMessageList.tsx    # US9 (AI-disclosure copy placement), if the
│   │                                #     reminder lives at the list/empty-state level
│   └── session/model/
│       └── session-store.ts       # US1 (only if root cause is thread_id related)
├── shared/
│   ├── config/
│   │   └── nav-routes.ts          # US8 (tab-bar overflow grouping)
│   ├── ui/layout/
│   │   └── TopBar.tsx             # US10 (back-button tap target)
│   └── api/                       # US1 (WS frame handling, if client-side fix)
└── pages/
    ├── workflows/, goals/          # US10 (humanized workflow/goal titles — display only)
```

Backend (only if Research, Unknown 1, concludes the root cause is server-side):

```text
core/ze-core/ze_core/... or apps/ze-api/ze_api/interface/native.py
```

**Structure Decision**: Single existing web app (`apps/ze-web`), FSD layout
already in place — no new project, package, or top-level directory is
created by this feature. This matches "Option 2: Web application" from the
template, scoped to only the `frontend/` (here, `apps/ze-web`) side, since no
new backend contract is being added.

## Complexity Tracking

*No entries — Constitution Check passed with no violations.*
