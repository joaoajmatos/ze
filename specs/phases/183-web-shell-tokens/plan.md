# Implementation Plan: Web Shell and Tokens (W1)

**Branch**: `183-web-shell-tokens` | **Date**: 2026-10-17 | **Spec**: [spec.md](spec.md)

**Input**: `specs/phases/183-web-shell-tokens/spec.md`; `apps/ze-web/.impeccable/plan/overhaul-plan.md` (Phase W1, decisions 1, 2, 5, 8, 9); `DESIGN.md`; reference build `apps/ze-web/src/pages/jarvis/`.

## Summary

Make the Jarvis direction the app's frame without rebuilding any place. Move `jarvis.css` to `shared/styles/ze.css` at `:root`, move the HUD primitives and the props-only orb/presence components to `shared/ui/hud`, replace `AppShell` with the HUD chrome (top bar with five places, strip, Presence, sticky Ask bar, phone bottom bar), drive the orb from a pure presence reducer over real WS signals, replace `nav-routes.ts` with `places.ts` plus a redirect table, and mount the old pages as interim sections inside their places. Delete the organ nav, the floating launcher and its overlay, and the prototype's private copies.

## Technical Context

**Language/Version**: TypeScript 5.9, React 19.2, react-router-dom 7.18, Vite, Tailwind 4 (kept only for interim pages), zustand 5.

**Primary Dependencies**: existing only. No new npm dependency. Fonts self-hosted as woff2 under `apps/ze-web/public/fonts/` (Saira, Michroma, JetBrains Mono, latin subset, OFL licence files beside them).

**Storage**: browser `localStorage` key `ze.palette` (try/catch on every access).

**Testing**: Vitest + Testing Library (`apps/ze-web/src/**/*.test.tsx`), `matchMedia` mocks for phone and reduced motion, `createMemoryRouter` for routes. Captures at 1440×900 and 390×844 through the impeccable capture flow (or the Maestri portal), console checked for errors.

**Target Platform**: `apps/ze-web` (desktop and phone browsers).

**Performance Goals**: scroll at 60 fps; the orb canvas pauses off-screen and on hidden tabs (`IntersectionObserver` + `visibilitychange`); no backdrop blur, no per-frame filters.

**Constraints**: FSD layer order `pages → widgets → features → entities → shared` (lint-enforced); `@myguyze/ze-client` types only; pre-v1 hard cut; DESIGN.md wins over the prototype CSS where they disagree (for example: no instrument ids outside Assemble, no prototype group in the top bar).

**Scale/Scope**: one engineer, one floor. About 25 files moved or rewritten, about 12 deleted.

## Constitution Check

| Principle | Assessment |
|---|---|
| I. Spec-First | PASS: spec written from the user-decided plan; two open questions listed for the user with recommendations |
| II. Single-User | PASS |
| III. Layered Packages | PASS: ze-web only; FSD layers respected (presence model in `entities`, ask-bar in `features`, chrome in `widgets`, primitives in `shared`) |
| IV. Typed | PASS: TS strict; no backend change |
| V. Test Discipline | PASS: reducer, router table, phone layout, palette, reduced motion tests written first |
| VI. Explicit Persistence | N/A (browser preference only) |
| VII. One Gateway | N/A |
| VIII. Pre-v1 Hard Cuts | PASS with a note: interim pages are mounted inside places so the app stays usable; they are not a compatibility layer (no API kept for old callers) and each later phase deletes its place's interim file (FR-012). The old routes redirect for external links only (ntfy, bookmarks); the app's own links are rewritten (FR-014) |

## Blast radius

ze-web has no graphify AST coverage worth trusting for TS; the radius below is from `rtk proxy grep -rln` on 2026-10-17 (main 586bcce3).

| Symbol changed | Importers |
|---|---|
| `shared/config` `navRoutes`, `settingsNavRoute`, `getRoute`, `getRouteLabel`, `settingsDataPath`, `settingsDataSectionId`, group arrays and icons (replaced by `places.ts`) | `git grep` 2026-10-17: `app/router/routes.ts`, `shared/config/index.ts`, `shared/config/nav-routes.ts` (+ test), `widgets/app-shell/ui/{AppShell,TopBar}.tsx`, `widgets/data-overview/ui/DataOverview.tsx`, `widgets/settings-workspace/ui/SettingsWorkspace.tsx`; `features/open-context-overlay/model/resolve-screen.ts` (moves to ask-bar) |
| `redirectHintPath` / hash deep links | `shared/lib/redirect-hint.ts`, `shared/ui/layout/RedirectHintTarget.tsx`, `shared/config/nav-routes.ts` |
| Old-path literals and `navigate("/")` meaning chat (FR-014) | `entities/goal/ui/GoalCard.tsx`, `entities/workflow/ui/WorkflowCard.tsx`, `pages/goal-detail/ui/GoalDetailPage.tsx`, `pages/workflow-detail/ui/WorkflowDetailPage.tsx`, `widgets/app-shell/ui/NotificationBell.tsx`, `widgets/app-shell/lib/notification-format.ts` (+ test), `pages/plugin-page/ui/PluginPage.tsx`, `shared/ui/layout/ZeErrorFallback.tsx`, `pages/jarvis/model/world.ts`, `pages/jarvis/hud/Cards.tsx` |
| `features/open-context-overlay` (deleted) | `widgets/goals-overview/ui/GoalsOverview.tsx`, `widgets/workflows-overview/ui/WorkflowsOverview.tsx`, `widgets/costs-overview/ui/CostsOverview.tsx` (+ test), `widgets/plugin-screen/ui/PluginScreen.tsx` (+ test) — `FloatingButton`; `pages/workflow-detail/ui/WorkflowDetailPage.tsx` (+ test) — `useOverlayStore.openForExecution`; `widgets/chat-workspace/ui/ContextOverlay.tsx` (+ `ContextOverlay.test.tsx`); `widgets/app-shell/ui/AppShell.tsx` — `useOverlay` |
| `ContextOverlay` (deleted) | `app/router/index.tsx`, `widgets/chat-workspace/index.ts` |
| `AppShell` (rewritten; `overlay` prop removed) | `app/router/index.tsx`, `widgets/app-shell/ui/AppShell.test.tsx` |
| `entities/ui-manifest` `mergeMobileNavRoutes` (deleted), `pluginNavRoutes` (kept for the `/:pluginPath` route) | `widgets/app-shell/ui/AppShell.tsx`, `entities/ui-manifest/model/merge-nav-routes.ts` (+ test if any) |
| `pages/jarvis/hud/*` (moved) and the `/jarvis/*` route (nested under the shell) | `pages/jarvis/{JarvisApp,JarvisShell,views/WorldView,views/AssembleView,hud/Cards,hud/FieldChart}.tsx`, `app/router/index.tsx` |
| Cross-floor files shared with phase 184 | `widgets/app-shell/lib/notification-format.ts` (owned here: `notificationHref`), `widgets/goals-overview/ui/GoalsOverview.tsx` (183 T012 removes `FloatingButton` before 184 T026 adds progress fields), docs `AGENTS.md`, `specs/README.md`, `docs/native-interface.md` (one Docs Steward pass for both floors, merge order set by the Maestro) |
| `app/styles/globals.css` `@theme` (remapped) | every Tailwind class in interim pages (visual only; no API) |

No Python, REST, WS or generated-client change. `make codegen` is not run.

## Design

### Tokens (`shared/styles/ze.css`)

Copy `pages/jarvis/jarvis.css` verbatim, then: replace the `.jarvis` scope by `:root` and `.jarvis[data-palette=…]` by `:root[data-palette=…]`; move `body` background and `color-scheme: dark` to `html, body`; drop the prototype-only selectors (`.proto`, `.proto-disclosure`, `.orb-ctl`, `.swatch`, `.sw-name`); keep every other class. `globals.css` imports it after Tailwind and remaps the `@theme` variables (FR-003). One audit pass: no rule still assumes a `.jarvis` ancestor (`rtk proxy grep -n "\.jarvis" src` returns nothing outside comments).

### `shared/ui/hud/`

One file per component from `pages/jarvis/hud/Frame.tsx` and `DotMatrix.tsx`: `Glyph`, `Spark`, `Decode`, `Corners`, `Module`, `Meter`, `Dots`, `CountUp`, `DotMatrix`, plus new thin wrappers that encode the `.ctl` rules: `Control` (`as="button" | "link"`, `pressed`, `current`, `primary`), `CommandChip` (index, label, key hint; keys 1–3 handled by the caller), `Chip` (`solid` | `dotted`). `Decode` and `CountUp` take `reducedMotion` from a `useReducedMotion()` hook in `shared/lib` (moved from `JarvisShell`). `Module`'s `index` prop stays, documented as Assemble-only.

### `shared/ui/hud/presence/`

Props-only, so it lives in `shared` (FSD forbids `widgets/app-shell` importing another widget). `Orb.tsx` (unchanged algorithm; colours read from computed `--main/--cream/--coral/--dim` on the root at mount and on palette change via a `MutationObserver` on `data-palette`), `LeaderLine.tsx`, `noise.ts`, `Presence.tsx` (props: `state`, `phrase`, `compact`; the session clock moves with it). The `statePhrase(state, world)` prototype helper is replaced by the phrase from `usePresence()`.

### `entities/presence/`

`model/presence.ts`: `type PresenceEvent`, `nextPresence(state, event, now)` pure; `done` carries `until` and the hook moves it to `idle` with one timeout. `model/usePresence.ts`: `usePresence(activeThreadId: string | null)`. Thinking and phrase from `useWsStore` `thinkingThreads[activeThreadId]` / `typingTextThreads[activeThreadId]`; speaking from `useFrame("token")` frames whose `thread_id === activeThreadId` (null `thread_id` ignored); done from a `message` frame for that thread; connection status from `useWsStore`. Replayed unread messages, proactive messages, notifications and other threads are ignored. `widgets/app-shell` passes `useSession()`'s active thread (widgets → entities is allowed; entities/presence never imports entities/session). `ask_*` events are dispatched by `features/ask-bar` through `presenceActions`.

### `features/ask-bar/`

`ui/AskBar.tsx`, `model/resolve-screen.ts` (moved, keyed on `placeOf`), `model/pending-ask.ts` (zustand: `{ text, context } | null`), `askAbout({ text, context })`. Submit on a non-Ask place: set `pendingAsk`, `navigate("/ask")`. `widgets/chat-workspace` consumes `pendingAsk` once on mount (send through its existing send path on the active thread, then clear). That consumer is the only edit inside `chat-workspace` besides the overlay deletion.

### `widgets/app-shell/`

`AppShell.tsx` rewritten: `TopBar` (brand, `PlaceTabs`, `NotificationBell`, `ConnectionDot`), `Strip`, grid with left rail (`Presence`) and hero (`<Outlet/>`), `AskBar` (hidden on `/ask`), `BottomBar` (≤1023 px). Keeps `RefreshHandler`, `ConfirmationFrameHandler`, `NoticeBanner` and the breadcrumb/page-header providers for interim pages. `useNarrow()` and `useReducedMotion()` come from `shared/lib`.

### Router (`app/router/`)

`routes.ts` builds children from `places.ts`: `index` → `WorldInterim`; `world/priority`; `ask`, `ask/:threadId`; `doing` (+ `goals`, `goals/:goalId`, `workflows`, `workflows/:workflowId`, `skills`, `procedures`, `workspace`); `mind` (+ `graph`); `governance` (+ `data`, `settings`); `/:pluginPath`. Redirects are element routes generated from the table in `places.ts`: `{ path: from, element: <RedirectTo to={target} /> }`, where `RedirectTo` (in `app/router/`) reads `useParams()` and `useLocation()` and renders `<Navigate replace to={target(params) + location.search + location.hash} />`. Not loaders: react-router 7.18 strips the hash from a client loader's request URL. `jarvis/*` is a child of the shell route (no longer top-level). `ask/:threadId` passes `threadId` to `ChatWorkspace` (`useChatWorkspace` already accepts an override).

### Interim places (`pages/<place>/`)

New pages `world`, `ask`, `doing`, `mind`, `governance`, each with `ui/<Place>Interim.tsx` holding the section switcher and lazy imports of the old pages, and `index.ts`. Governance's Settings section renders the palette control above `SettingsPage` (`features/choose-palette`).

## Project Structure

### Documentation (this feature)

```
specs/phases/183-web-shell-tokens/
├── spec.md
├── plan.md
└── tasks.md
```

### Source Code

```
apps/ze-web/src/
├── app/router/{index.tsx,routes.ts}          # rewritten
├── app/styles/globals.css                     # fonts, @theme remap, imports ze.css
├── shared/styles/ze.css                       # NEW (from jarvis.css)
├── shared/config/places.ts (+ test)           # NEW, replaces nav-routes.ts
├── shared/lib/{use-reduced-motion,use-narrow}.ts  # NEW (moved hooks)
├── shared/ui/hud/*.tsx (+ tests)              # NEW (moved primitives)
├── shared/ui/hud/presence/                    # NEW (Orb, Presence, LeaderLine, noise)
├── public/fonts/                              # NEW (self-hosted woff2 + OFL)
├── main.tsx                                   # palette applied before createRoot
├── entities/presence/                         # NEW
├── features/ask-bar/                          # NEW (resolve-screen moved here)
├── features/choose-palette/                   # NEW
├── widgets/app-shell/                         # rewritten
├── pages/{world,ask,doing,mind,governance}/   # NEW interim places
└── pages/jarvis/                              # re-pointed at shared/ui; css + hud copies deleted
```

## Docs touched ([DOCS] tasks)

- `docs/frontend.md`: shell, five places, tokens location (`shared/styles/ze.css`), `shared/ui/hud`, presence states, redirect table, interim places.
- `apps/ze-web/README.md`: routes, design system pointer (`DESIGN.md`).
- `docs/native-interface.md`: the contextual chat overlay is gone; the Ask bar sends `context.screen` (and `workflow_id`/`execution_id` from workflow detail).
- `DESIGN.md` Navigation section: top bar is five places, no prototype group; phone bottom bar.
- `AGENTS.md` (Learned facts: web nav groups line is now five places; phase table row 183) and `specs/README.md` index row.
- Coverage check against `git diff main...HEAD --stat`.

## Complexity Tracking

| Item | Why | Simpler alternative rejected |
|---|---|---|
| Interim sections per place | Keeps every commit usable while places are rebuilt across six floors | Keeping the old shell until W2–W6 land contradicts decision 1 for weeks; empty places lose features |
| Tailwind `@theme` remap | Interim pages are Tailwind; remapping keeps them legible in the new palette with zero edits to them | Restyling each interim page wastes work that its own phase deletes |
