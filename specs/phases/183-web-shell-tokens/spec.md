# Feature Specification: Web Shell and Tokens (W1)

**Feature Branch**: `183-web-shell-tokens`

**Created**: 2026-10-17

**Status**: Ready to implement (approved by the Floor Reviewer Gauge, c9639732; user answers recorded 2026-10-17, OQ-2 amended — re-check pending)

**Input**: Maestro brief 2026-10-17: "turn the plan into speckit phases … 183 W1 Shell and tokens." Source: `apps/ze-web/.impeccable/plan/overhaul-plan.md` section e, Phase W1, with the user's decisions in section f ("go with the recommendations", all nine accepted). Design system: `DESIGN.md` (repo root). Product truth: `PRODUCT.md`. Reference build: `apps/ze-web/src/pages/jarvis/` (route `/jarvis`).

**Governed by**: `DESIGN.md` (tokens, components, motion, The One Alarm / Four Levels / Light rules), `PRODUCT.md` (principles 1 and 5), `specs/arch/pre-v1-hard-cuts.md`, the FSD rules in `AGENTS.md` (ze-web section). User's binding rule: "Ze is not an agenda or notes app; every view answers 'what does Ze understand, and what is it doing about it?'".

**Depends on**: nothing. Runs in parallel with 184 (B1).

**Followed by**: 186 World (W2), 187 Ask/Assemble (W3), 188 Doing (W4), 189 Mind (W5), 190 Governance (W6). Each of those replaces the interim content this phase mounts in its place (FR-012) and deletes the old page it replaces.

**Doctrine function served**: governance (the web app is how the user sees and governs the one world-state). The shell itself adds no capability; it is the frame every later place renders in.

---

## Overview

ze-web today is a left nav of 13 routes grouped by organ (Automation, Knowledge, System, Plugins), a chat as the home screen, a floating "Ze" launcher that opens a contextual chat overlay on every page, and a generic dark Tailwind theme (Space Grotesk, Inter, purple pills on rounded cards). The design direction the user chose on 2026-10-17 (GMUNK HUD + Nothing OS dot matrix, purple-led, the orb as Ze's presence) exists only as a prototype at `/jarvis`, with its tokens scoped to `.jarvis` and its components under `pages/jarvis/hud/`.

This phase makes that direction the app's frame. It moves the tokens to the app stylesheet, moves the HUD building blocks to `shared/ui`, and replaces the shell with the HUD chrome: a top bar with the five places (World, Ask, Doing, Mind, Governance), a one-line strip, the Presence module with the orb, a sticky Ask bar on every screen that opens a contextual overlay where the answer arrives without leaving the screen (the exchange is a real Ask thread), and a five-icon bottom bar on phones. The router gains the five place routes and every old route redirects into its place.

The five places do not get their new content here. Each place mounts the existing pages it will absorb as interim sections (World hosts Open loops and Priority, Doing hosts Goals, Workflows, Skills, Procedures and Workspace, and so on), restyled only through the shared tokens, until its own phase replaces them. That keeps the app usable on every commit while the places are rebuilt one floor at a time.

## Clarifications

### Session 2026-10-17 (from the plan, decided by the user)

- Q: What is the home? → A: **(user, decision 1)** World at `/`; Ask lives at `/ask`; the Ask bar is on every screen.
- Q: Which places? → A: **(user, decision 2)** World · Ask · Doing · Mind · Governance. "Open loops", "goals", "workflows" stay as module names inside them.
- Q: Palette? → A: **(user, decision 5)** a user setting in Governance; Orchid is the default; Ultraviolet and Amethyst remain.
- Q: Phone navigation? → A: **(user, decision 8)** a bottom tab bar with five icons; the Ask bar sits above it.
- Q: Instrument ids (A·02, G·01)? → A: **(user, decision 9)** dropped everywhere except the Assemble canvas.

### Session 2026-10-17 (Floor Reviewer Gauge, changes applied)

- Redirects use `<Navigate>` element routes (loaders lose the hash in react-router 7.18). Presence components live in `shared/ui/hud/presence` (FSD forbids widget → widget). The orb follows the active thread's per-thread WS state only. `/jarvis/*` nests under the shell. Fonts are self-hosted. `notificationHref` is owned by this phase, built from the 184 target table. The palette applies before first render in `main.tsx`. `ask/:threadId` passes the thread to `ChatWorkspace`.

### Session 2026-10-17 (user answers, relayed by the Maestro)

- Q (OQ-1): Between this phase and each place's own phase, what renders inside a place? → A: **(user)** the existing pages, mounted as interim sections of their place under the final URL scheme (FR-012), restyled only by the shared tokens (the Spec Architect's recommendation).
- Q (OQ-2): What does the Ask bar do on a screen other than Ask? → A: **(user, changed from the recommendation)** "contextual overlay but also creates a chat in ask". Typing in the Ask bar on a non-Ask screen opens a contextual overlay over the current screen, where the answer arrives and the user stays in place. The exchange is a real chat thread in Ask (same `thread_id`, each message carrying `context.screen`), so it shows in Ask's sessions and can be reopened there. Split decided by the Spec Architect: **this phase** builds the overlay shell and the thread behaviour (open/close, send on the thread, streamed reply text, the reply's components through the existing renderer, "Open in Ask", "New chat"); **phase 187** gives the overlay the full assembly (the same canvas as `/ask`: cascade from the orb, module frames, trace chip, confirmation card in place, Retry). FR-008, FR-008a, FR-015 and US6 encode it.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The app opens on the HUD with five places (Priority: P1)

The user opens Ze. The page is the near-black plum field with the dot-matrix "ZE" brand, five tabs (World, Ask, Doing, Mind, Governance), a one-line strip (claim legend, date, dot-matrix session clock), the Presence module with the orb at the top of the left rail, and the sticky Ask bar at the bottom. `/` is World. There is no left nav of organ groups and no floating launcher.

**Why this priority**: It is the phase's reason to exist and the frame for every later phase.

**Independent Test**: Render the router at `/`, `/ask`, `/doing`, `/mind`, `/governance` in Vitest: each shows the top bar with five tabs, the current tab marked `aria-current="page"`, the strip, the Presence module and (except on `/ask`) the Ask bar. Capture at 1440×900 with the impeccable/Playwright capture flow: no console errors.

**Acceptance Scenarios**:

1. **Given** a configured client, **When** the user opens `/`, **Then** the World tab is current and the Presence module and Ask bar are visible.
2. **Given** any place, **When** the user presses `/` outside a text field, **Then** focus moves to the Ask bar input (on `/ask`, to the chat composer).
3. **Given** the codebase, **When** searched, **Then** `NavGroup`, `ChatNavGroup`, the organ group arrays (`automationNavRoutes`, `knowledgeNavRoutes`, `systemNavRoutes`), `FloatingButton`, `ContextOverlay`, `features/open-context-overlay` and the Cmd-K overlay shortcut no longer exist (the overlay is rebuilt as `AskOverlay`, FR-008a).

---

### User Story 2 - Every old route lands in its place (Priority: P1)

Links in notifications, bookmarks and ntfy deep links point at old routes (`/goals/…`, `/workflows/…`, `/loops`, `/brain-memory`, `/settings#your-data`). Each redirects to the same content under its place, keeping the id, query string and hash.

**Why this priority**: ntfy pushes and the notification bell link to these paths today; a broken link is a lost decision.

**Independent Test**: A table-driven router test: for every row of the redirect table (FR-011), navigating to the old path ends at the new path with params, query and hash preserved, and renders the interim section.

**Acceptance Scenarios**:

1. **Given** `/goals/7f…`, **When** opened, **Then** the URL becomes `/doing/goals/7f…` and the goal detail renders.
2. **Given** `/settings#your-data`, **When** opened, **Then** the URL becomes `/governance/settings#your-data` and the data section scrolls into view.
3. **Given** a plugin manifest path (for example `/contacts`), **When** opened, **Then** it still renders the plugin page inside the HUD shell (plugin placement into places is phase 191, W7).

---

### User Story 3 - Ze's presence is visible and honest (Priority: P1)

The orb in the Presence module shows what Ze is doing right now, from real signals only: idle at rest; listening while the Ask bar has focus and text; thinking from the `typing` frame of a turn until its first `token`; speaking while tokens stream; done for one bloom when the `message` frame closes the turn; error (dim, coral limb, "Offline") while the WebSocket is closed. The state phrase under the orb says it in words ("listening", "thinking", "Offline"). Attention and acting states exist in the component but nothing in this phase drives them (World and Doing do).

**Why this priority**: The orb is the presence (DESIGN.md "signature"); it must never show a state that is not true.

**Independent Test**: Unit-test the pure presence reducer `nextPresence(state, event)` over the WS events (connection open/closed, typing, token, message, error, ask focus/blur/text) and the orb's pure helpers (`heartbeat`, the stagger function). Render `Presence` with `prefers-reduced-motion: reduce` mocked: the canvas draws one frame and schedules no animation frame after it.

**Acceptance Scenarios**:

1. **Given** the WebSocket closes, **When** the shell renders, **Then** the orb is in `error`, the phrase reads "Offline", and every write control in the shell (Ask submit) is disabled with "Ze is offline" in its accessible name.
2. **Given** a turn in flight, **When** the `typing` frame arrives, **Then** the orb is `thinking` and the phrase shows `typing.text` when present; on the first `token` it is `speaking`; on `message` it blooms (`done`) and settles to `idle`.
3. **Given** reduced motion, **When** any state is set, **Then** the orb is a still frame and no `requestAnimationFrame` loop runs.
4. **Given** the tab is hidden or the orb is off-screen, **When** time passes, **Then** the canvas loop is paused.

---

### User Story 4 - Phone width works (Priority: P1)

At 390 px the layout is one column with 16 px gutters and no horizontal scroll. The five places sit in a bottom bar with five icons and labels; the Ask bar sits directly above it. The Presence module is compact (150 px orb) and comes first.

**Why this priority**: The user reads Ze on a phone daily (PRODUCT.md Users).

**Independent Test**: Vitest with `matchMedia('(max-width: 1023px)')` mocked true: the bottom bar renders five links with accessible names, the top tabs are hidden, and the Ask bar renders above the bottom bar. Capture at 390×844: `document.documentElement.scrollWidth <= 390`, every interactive element ≥ 44×44 px.

**Acceptance Scenarios**:

1. **Given** a 390 px viewport, **When** any place renders, **Then** there is no horizontal scroll and the bottom bar shows World, Ask, Doing, Mind, Governance.
2. **Given** the phone layout, **When** the user taps a bottom-bar item, **Then** it navigates and marks the item current.

---

### User Story 5 - The palette is a Governance setting (Priority: P2)

The palette switcher (Orchid, Ultraviolet, Amethyst) lives in Governance. Choosing one swaps `--main`, `--field`, `--dim`, `--coral`, `--cream` on the root at once, persists in the browser, and survives reload. Orchid is the default.

**Why this priority**: User decision 5; small, but the prototype's switcher must leave the top bar.

**Independent Test**: Render the Governance palette control, pick Amethyst: `document.documentElement.dataset.palette === "amethyst"` and the stored value is `amethyst`; remount: still Amethyst. With storage throwing, the default Orchid renders and nothing crashes.

**Acceptance Scenarios**:

1. **Given** a fresh browser, **When** the app loads, **Then** `data-palette="orchid"` is on the root.
2. **Given** storage access throws, **When** the palette is read or written, **Then** the app renders with Orchid and logs nothing to the user.

---

### User Story 6 - Ask from anywhere without leaving the screen (Priority: P1)

On `/doing/goals/7f…` the user types "why is this stuck?" in the Ask bar and presses Enter. A contextual overlay opens over the current screen (desktop: a framed module anchored above the Ask bar on the right of the hero; phone: a sheet above the Ask bar and bottom bar, at most 65% of the height). The message is sent on the thread selected in Ask with `context.screen` and `goal_id`; the reply streams into the overlay with its components below it. The Ask bar stays the input for follow-ups. "Open in Ask" goes to `/ask/<thread>` where the same exchange is in the thread and in Sessions. "New chat" starts a fresh thread (selected in Ask too). Esc or Close dismisses the overlay; the page underneath never navigated.

**Why this priority**: The user's decision (OQ-2): ask in place, keep the exchange in Ask.

**Independent Test**: Render the shell at `/doing/goals/g1` with a fake WS: submitting "why?" opens `AskOverlay`, sends exactly one `message` frame with the selected thread id and `context: { screen: "doing.goals", goal_id: "g1" }`, and the location is unchanged; a `token` then `message` frame for that thread render in the overlay; "Open in Ask" navigates to `/ask/<thread>`; "New chat" calls `newSession()` and the next submit uses the new id.

**Acceptance Scenarios**:

1. **Given** the thread currently selected in Ask (`useSession().threadId`, always set), **When** the user asks from any place, **Then** the message goes on that thread, so opening Ask shows the exchange in place; "New chat" (`newSession()`) is the only way the overlay starts a fresh thread.
2. **Given** the overlay is open, **When** the user navigates to another place, **Then** the overlay stays open on the same thread and the next message carries the new screen's context.
3. **Given** a `confirm_request` for the overlay's thread, **When** it arrives, **Then** the existing confirmation card renders (restyled by tokens; its in-overlay placement is phase 187).
4. **Given** `/ask`, **When** it renders, **Then** neither the Ask bar nor the overlay is shown (the old chat page owns input until 187).

### Edge Cases

- Not configured (no server URL or API key): the existing first-run setup screen (`OnboardingWizard`) renders before the router, unchanged in behaviour, restyled only through tokens. Conversational onboarding (`command: onboarding`) is phase 187.
- Unknown path that matches no place, no redirect and no plugin manifest entry: the existing `RouteErrorPage`, inside the HUD shell, with a "Back to the world" command chip.
- `/jarvis`: stays reachable as the design reference (deleted in phase 193, W8). Its route is nested under the shell (`AppShell` children, `jarvis/*`), so it renders in the real chrome from the moved `shared/ui` components and `ze.css`; its private copies and `JarvisShell` chrome (top bar, strip, Ask form, proto group) are deleted (FR-004, FR-015). `JarvisShell` shrinks to the context provider its views read, with fields `palette` (read from the root `data-palette`), `orb`/`setOrb` (initialised from `usePresence()`, overridable by a view for the demo), `reducedMotion`, `narrow`, `colors` (computed from the root).
- A confirmation request arrives while the user is on any place: the existing `ConfirmationFrameHandler` keeps rendering the confirmation card (restyled by tokens); its redesign is phase 187.
- The notification bell keeps its unread count and panel (`NotificationBell`), moved into the new top bar.
- Reduced motion: still orb, no decode/count-up/draw-on/sweep, transitions at 150 ms (DESIGN.md Motion).

## Requirements *(mandatory)*

### Functional Requirements

**Tokens and type**

- **FR-001**: `apps/ze-web/src/shared/styles/ze.css` MUST be the app stylesheet. It holds every token and class from `pages/jarvis/jarvis.css`, re-scoped from `.jarvis` to `:root` (palette by `:root[data-palette="…"]`), and is imported once from `app/styles/globals.css`. `jarvis.css` is deleted.
- **FR-002**: Fonts MUST be Saira (200/300/400), Michroma (400) and JetBrains Mono (300/400), self-hosted: the woff2 files (latin subset) and their OFL licence texts live in `apps/ze-web/public/fonts/` and are declared with `@font-face` in `ze.css` (Ze runs locally; no third-party request per page load; no new npm dependency). Space Grotesk and Inter MUST be removed from `globals.css` and the Tailwind theme, including the Google Fonts `@import`.
- **FR-003**: The Tailwind `@theme` colour, font and radius variables in `globals.css` MUST be remapped onto the new tokens (for example `--color-background: var(--field)`, `--color-foreground: var(--ink)`, `--color-plum-voltage: var(--main)`, `--color-ember: var(--coral)`, `--font-sans` and `--font-display: Saira…`, `--radius-pill: 0px`, `--radius: 0px`) so interim pages stay legible in the new palette. No new Tailwind styling is written for the shell; the shell uses `ze.css` classes. The remap is deleted by whichever of phases 186–190 deletes the last interim page.

**Shared HUD components**

- **FR-004**: `shared/ui/hud/` MUST hold the HUD building blocks moved from `pages/jarvis/hud/` and split one component per file: `Module`, `Corners`, `Meter`, `Dots`, `Spark`, `Glyph`, `Decode`, `CountUp`, `DotMatrix`, `CommandChip`, `Control` (the `.ctl` button, link and tab), `Chip`. They are exported from `shared/ui/index.ts`. The jarvis page imports them from `@/shared/ui`; its private copies are deleted. `Module` takes an optional `index` that only the Assemble canvas passes (decision 9).
- **FR-005**: `shared/ui/hud/presence/` MUST hold `Orb.tsx`, `Presence.tsx`, `LeaderLine.tsx` and the pure `noise.ts`, moved from `pages/jarvis/hud/`. They are props-only (no store reads), so they belong in `shared` and both `widgets/app-shell` and `pages/jarvis` import them without a same-layer cross-slice import (the FSD lint forbids widget → widget). `Presence` takes the orb state and the phrase as props and no longer reads the prototype `World` model. The prototype's `useAmbience` stays in `pages/jarvis` (ambience is phase 193).
- **FR-006**: The presence state MUST be derived by a pure reducer `nextPresence(state, event)` in `entities/presence/model/`, exposed as `usePresence()`. Turn phases come from the **active thread** only. `usePresence(activeThreadId: string | null)` takes the thread as an argument (`widgets/app-shell` reads it from `useSession` in `entities/session` and passes it down; an entity never imports another entity). Thinking and its phrase come from the per-thread entries already in `useWsStore` (`thinkingThreads`, `typingTextThreads`); speaking comes from `useFrame("token")` filtered to `thread_id === activeThreadId` (a frame with a null `thread_id` is ignored: an unattributed token cannot be shown as the active thread's); done comes from a `message` frame for that thread. Replayed unread messages on connect, proactive messages, notifications and frames for other threads never move the orb. Events: `ws_open`, `ws_closed`, `ask_focus`, `ask_blur`, `ask_text(nonEmpty)`, `turn_thinking(text?)`, `turn_token`, `turn_message`, `turn_error`, each derived for the active thread only; with `activeThreadId` null, turn events are not derived. `turn_message` yields `done` only when the previous state was `thinking` or `speaking` for that thread. States driven in this phase: `idle`, `listening`, `thinking`, `speaking`, `done` (one bloom, then `idle` after 1 s), `error`. `attention`, `acting` and `assembling` are accepted by the reducer API (`set_world_signal`) but no caller sends them until phases 186 and 188.

**Shell**

- **FR-007**: `widgets/app-shell` MUST become the HUD chrome: top bar (dot-matrix "ZE", five place tabs as `Control` tabs with `aria-current`, the existing `NotificationBell`, a connection dot with an accessible name), the strip (claim legend; date; dot-matrix clock), a desktop grid `264px minmax(0,1fr)` with the Presence module at the top of the left rail and the place's content in the hero column, and the sticky Ask bar. No page title is duplicated below the top bar (`PAGE_HEADER` providers stay only for interim pages that still read them).
- **FR-008**: The Ask bar (`features/ask-bar`) MUST be a 44 px input with an Ask control and a disabled mic control labelled "Voice input arrives later" (voice is phase 193). On submit from any place except Ask it opens the overlay (FR-008a) and sends the text as a `message` frame on the overlay thread with `context` resolved from the current route: `screen` (from today's `features/open-context-overlay/model/resolve-screen.ts`, moved and re-keyed to place ids such as `world`, `doing.goals`, `doing.workflows`, `mind`, `governance`) plus `goal_id` / `workflow_id` / `execution_id` from the route params. On `/ask` the bar is not rendered. `/` focuses it outside text fields. It is disabled while offline (FR-006 `error`). `askAbout({ text?, context })` opens the overlay with the bar prefilled (not sent) and the given context (used by workflow detail's "Ask about this run").
- **FR-008a**: The overlay MUST be `AskOverlay` in `widgets/chat-workspace/ui/` (rewritten from `ContextOverlay`, which it replaces), passed to `AppShell` through its `overlay` prop from `app/router` (so no widget imports another widget). Its state (`open`, `context`, `prefill`) lives in `features/ask-bar/model/ask-overlay.ts`. Thread: the overlay uses `useSession().threadId`, the thread Ask shows (the store always holds one, persisted under `ze_current_thread_id`). "New chat" calls `useSession().newSession()`. The separate `ze_overlay_thread_id` localStorage thread is deleted. Content in this phase: the thread's messages from the moment the overlay opened (earlier history stays in Ask), streamed reply text, typing phrase, each reply's components through the existing `PrimitiveRenderer` path the chat uses today, "Open in Ask" (`askPath(thread)`), "New chat", Close (button and Esc). HUD styling from `ze.css` (module frame, corners, no backdrop blur, no drag handle). The presence orb follows the overlay's thread (it is the selected thread). Full assembly in the overlay is phase 187.
- **FR-009**: At ≤ 1023 px the shell MUST be one column with 16 px gutters, `overflow-x: clip` on the root, the Presence module first and compact (150 px), the top tabs hidden, and a fixed bottom bar with five icon+label links (44 px targets). The Ask bar sits above the bottom bar. No backdrop blur (DESIGN.md).
- **FR-010**: The palette control MUST live in Governance (interim: a section at the top of `/governance/settings`). It writes `data-palette` on `document.documentElement` and stores the choice under `ze.palette` in `localStorage`, every access wrapped in try/catch; default `orchid`. The stored palette is applied synchronously in `main.tsx` before `createRoot` (no flash of the default palette). The prototype's `jarvis.palette.v2` key is not read.

**Routes**

- **FR-011**: The router MUST declare the five places and redirect every old route, preserving path params, query and hash:

  | Old | New |
  |---|---|
  | `/` (chat) | `/ask` is chat; `/` is World |
  | `/loops` | `/` (World › Open loops section) |
  | `/priority` | `/world/priority` (interim; deleted in phase 186) |
  | `/goals`, `/goals/:goalId` | `/doing/goals`, `/doing/goals/:goalId` |
  | `/workflows`, `/workflows/:workflowId` | `/doing/workflows`, `/doing/workflows/:workflowId` |
  | `/skills` | `/doing/skills` |
  | `/procedures` | `/doing/procedures` |
  | `/workspace` | `/doing/workspace` |
  | `/brain-memory` | `/mind` |
  | `/brain-graph` | `/mind/graph` |
  | `/costs` | `/governance` |
  | `/data` | `/governance/data` |
  | `/settings` | `/governance/settings` |

  Plugin manifest paths keep their `/:pluginPath` route inside the shell. `ask/:threadId` passes `threadId` to `ChatWorkspace` (whose `useChatWorkspace` already accepts a thread override). `/jarvis/*` is nested under the shell (see Edge Cases).

  Redirects MUST be element routes, not loaders: a `RedirectTo` component in `app/router/` reads `useParams()` and `useLocation()` and renders `<Navigate replace to={target(params) + location.search + location.hash} />`. (In react-router 7.18 a client loader's `request.url` has the hash stripped, so a loader redirect loses `#your-data`.) The table itself is data in `shared/config/places.ts`.
- **FR-012**: Until its own phase lands, each place MUST render its interim sections behind a section switcher (a row of `Control` tabs, the first section as the index): World (`Open loops` → `LoopsPage`, `Priority` → `PriorityPage`); Ask (`ChatPage`); Doing (`Goals`, `Workflows`, `Skills`, `Procedures`, `Workspace`); Mind (`Memory` → `BrainMemoryPage`, `Graph` → `BrainGraphPage`); Governance (`Usage` → `CostsPage`, `Data`, `Settings`). The section switcher and the interim mapping live in one file per place (`pages/<place>/ui/<Place>Interim.tsx`) so each later phase deletes one file.
- **FR-013**: `shared/config/nav-routes.ts` MUST be replaced by `shared/config/places.ts`: the five `Place` records (`id`, `path`, `label`, `icon`), `placeOf(pathname)`, the redirect table as data, and path helpers `goalPath(id)`, `workflowPath(id, executionId?)`, `askPath(threadId?)`, `settingsDataPath()`. `getRoute`/`getRouteLabel` callers move to it in the same change.
- **FR-014**: The app's own links MUST build the new paths directly through the FR-013 helpers; the redirects exist for external links (ntfy, bookmarks), not for the app's own links. Because `/` changes meaning (chat → World), every `navigate("/")` that meant "the chat" becomes `askPath()`. Known sites (2026-10-17 grep; T010 re-runs `git grep -nE 'navigate\(|to=|href=' -- apps/ze-web/src` and fixes every hit): `entities/goal/ui/GoalCard.tsx` (`/goals/${id}`), `entities/workflow/ui/WorkflowCard.tsx`, `pages/goal-detail/ui/GoalDetailPage.tsx` (`/goals`), `pages/workflow-detail/ui/WorkflowDetailPage.tsx` (`/workflows`; "View conversation" `navigate("/")` → `askPath(thread)`), `widgets/app-shell/ui/NotificationBell.tsx` (`chat_thread` → `askPath(thread)`), `pages/plugin-page/ui/PluginPage.tsx` and `shared/ui/layout/ZeErrorFallback.tsx` (`/` fallbacks stay World, deliberately), `shared/lib/redirect-hint.ts`, `shared/ui/layout/RedirectHintTarget.tsx`. Prototype links in `pages/jarvis/model/world.ts` and `hud/Cards.tsx` move with T017.
- **FR-014a**: Notification links MUST come from one function, `notificationHref(n: { target_type, target_id, target_parent_id? })` in `widgets/app-shell/lib/notification-format.ts`, implementing the target table in `specs/phases/184-composed-answers-posture/contracts/notification-targets.md` with the new paths (`target_parent_id` optional so it works before 184 lands). `NotificationBell` uses it. Phase 184 only adds `target_parent_id` to the generated type and table tests (cross-floor ownership: this phase owns the function).

**Hard cuts (pre-v1, nothing behind a flag)**

- **FR-015**: Deleted in this phase: `widgets/app-shell/ui/NavGroup.tsx` (+ test), `ChatNavGroup.tsx`, the desktop `<nav>` sidebar and the old mobile nav in `AppShell.tsx`; `features/open-context-overlay` (overlay store with its own `ze_overlay_thread_id` thread, and `ui/FloatingButton.tsx`; `model/resolve-screen.ts` moves to `features/ask-bar` per FR-008), with its callers updated in the same change: the `FloatingButton` usages in `GoalsOverview`, `WorkflowsOverview`, `CostsOverview` and `PluginScreen` are removed, and `WorkflowDetailPage`'s `openForExecution` becomes `askAbout({ text, context })` from `features/ask-bar` (opens the overlay prefilled, with the execution in `context`); `widgets/chat-workspace/ui/ContextOverlay.tsx` (+ test), replaced by `AskOverlay` (FR-008a); the Cmd-K overlay shortcut and the overlay's drag handle and own input; `shared/config/nav-routes.ts` (+ test, replaced per FR-013); `entities/ui-manifest` `mergeMobileNavRoutes` (the bottom bar is fixed at five places; plugin entries stay reachable by path and in phase 191 move into places); `pages/jarvis/jarvis.css`, `pages/jarvis/hud/{Frame,DotMatrix,Orb,Presence,LeaderLine,noise}.tsx|ts` (moved); the prototype top-bar group (palette, orb select, ambience) in `JarvisShell`, which now uses the real shell.
- **FR-016**: Not deleted here (their place's phase deletes them): every interim page and its widgets, `ConfirmationFrameHandler`, `NotificationBell`, `widgets/chat-workspace` except the overlay files, `shared/effects/*`, `pages/jarvis` views and model.

### Key Entities

- **Place**: `{ id: "world" | "ask" | "doing" | "mind" | "governance"; path; label; icon }`. Five, fixed, in that order.
- **Overlay thread**: the session-store selected thread; one thread at a time; messages carry `context.screen` per message.
- **PresenceState**: `{ orb: OrbState; phrase: string; offline: boolean }`, where `OrbState` is the nine-state union from DESIGN.md.
- **Redirect**: `{ from: string; to: string }` with `:param` segments carried across.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 13 old core routes and the old `/` redirect or resolve per FR-011; the router test covers every row.
- **SC-002**: At 1440×900 and 390×844, every place renders with zero console errors, no horizontal scroll, and every interactive element ≥ 44×44 px. jsdom cannot measure, so the capture run (T019) is the gate for sizes and scroll; unit tests assert the class-level contract (every shell control, tab and bottom-bar link carries `ctl`, whose CSS sets the 44 px minimum).
- **SC-003**: The impeccable detector reports 0 findings on `shared/ui/hud`, `widgets/app-shell`, `features/ask-bar`.
- **SC-004**: An impeccable critique of the shell (top bar, strip, presence, Ask bar, phone bar) scores at or above the `/jarvis` reference shell's score recorded at the start of the floor.
- **SC-005**: `make test-web`, `make typecheck-web`, `make web-build` and `bun run lint` (FSD boundaries) pass.
- **SC-006**: With reduced motion, no `requestAnimationFrame` callback is scheduled by the orb after its first frame.

## Assumptions

- `framer-motion` stays available for the cascade and layout motion used by later phases; this phase uses CSS transitions only.
- The self-hosted woff2 files load from the app origin; a missing font falls back to system-ui without layout breakage.
- The interim pages tolerate a hero column narrower than today's full width; layout bugs found in interim pages are not fixed here unless they block use (they are deleted by their place's phase).

## Out of Scope

- New content for any place (phases 186–190), the Assemble canvas and the trace module (187), the field chart and leader line wiring (186), voice and ambience (193), plugin placement into places (191).
- Backend changes. This phase touches no Python, no REST or WS contract, and no generated client.

## Verbatim Constraints

- "Ze is not an agenda or notes app; every view answers 'what does Ze understand, and what is it doing about it?'" (user, via the Maestro, 2026-10-17)
- "go with the recommendations" (user, all nine plan decisions, 2026-10-17)
