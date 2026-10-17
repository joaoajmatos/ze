# Tasks: Web Shell and Tokens (W1)

**Input**: [spec.md](./spec.md), [plan.md](./plan.md), `DESIGN.md`, `apps/ze-web/.impeccable/plan/overhaul-plan.md`, reference build `apps/ze-web/src/pages/jarvis/`.

**Build gate**: open; the user answered OQ-1 and OQ-2 on 2026-10-17 (spec Clarifications). OQ-2 changed: the Ask bar opens a contextual overlay that is also a real Ask thread (FR-008, FR-008a, US6). The Spec Architect (Lintel) stays on call.

**Tests**: required (constitution V). **Fail-first**: write the test, run it, see it fail for the stated reason, then implement. Vitest + Testing Library; `matchMedia` mocks for phone (`(max-width: 1023px)`) and reduced motion; `createMemoryRouter` for routes; `useWsStore.setState` and a fake frame emitter for WS signals.

**Lanes**: `[ENG]` Claude Sonnet lane lead (owns shared files, integration and gates). `[JR]` OpenCode junior (exact files given). Floor Reviewer reviews per user story.

**Tags**: `[WEB]` ze-web · `[PLATFORM]` build/config · `[DOCS]` docs and specs. No `[BACKEND]` task in this phase.

**Rules for the implementer**
- FSD: `pages → widgets → features → entities → shared`; run `bun run lint` (boundaries) before each commit.
- Pre-v1 hard cut: delete what FR-015 lists in the same change that replaces it; no re-export shims for moved files (update importers).
- DESIGN.md wins over `jarvis.css` where they disagree; report each disagreement you resolve in the floor Handoffs note.
- No new Tailwind classes in the shell, `shared/ui/hud`, `features/ask-bar`; use `ze.css` classes.
- Every `localStorage` access in try/catch.
- Shared worktree: `git add <your paths>`; `git commit -m ... -- <paths>`. Never `git add -A` or `git stash`. Commit only when the ENG lead or Maestro asks; split commits by user story.

---

## Phase 0: Gate [ENG]

- [ ] T001 [ENG] [WEB] Rebase onto `main`. Record in the Handoffs note: (a) `rtk proxy grep -rln "open-context-overlay\|ContextOverlay\|FloatingButton\|nav-routes\|getRoute\|settingsDataPath\|mergeMobileNavRoutes" apps/ze-web/src` compared with plan.md "Blast radius"; (b) (dropped: the active thread comes from `useSession` in `entities/session`, passed into `usePresence` by the shell); (c) a baseline impeccable critique score of `/jarvis` (SC-004) and captures of `/jarvis` at 1440 and 390. Stop and report any difference to the Spec Architect.

## Phase 1: Tokens and type (blocks everything)

- [ ] T002 [ENG] [WEB] Create `apps/ze-web/src/shared/styles/ze.css` from `pages/jarvis/jarvis.css` per plan.md "Tokens": `:root` scope, palette selectors on `:root[data-palette]`, drop `.proto*`, `.orb-ctl`, `.swatch`, `.sw-name`. Import it from `app/styles/globals.css`. Add `shared/lib/palette.ts` (`readPalette()`, `applyPalette(id)`, `storePalette(id)`, all storage access in try/catch, default `orchid`) with tests, and call `applyPalette(readPalette())` in `main.tsx` before `createRoot` (FR-010).
- [ ] T003 [ENG] [WEB] Fonts (FR-002): add the woff2 files (latin subset) for Saira 200/300/400, Michroma 400, JetBrains Mono 300/400 and their OFL licence texts under `apps/ze-web/public/fonts/`; declare them with `@font-face` (`font-display: swap`) in `ze.css`. `app/styles/globals.css`: delete the Google Fonts `@import`; remap the `@theme` colour/font/radius variables onto the new tokens (FR-003); delete Inter/Space Grotesk references. Verify: `rtk proxy grep -rn "Space Grotesk\|Inter'\|fonts.googleapis" apps/ze-web/src` is empty.
- [ ] T004 [P] [JR] [WEB] Move `useReducedMotion` and `useNarrow` from `pages/jarvis/JarvisShell.tsx` to `shared/lib/use-reduced-motion.ts` and `shared/lib/use-narrow.ts` with tests (media-query change updates the value); export from `shared/lib/index.ts`.

## Phase 2: Shared HUD primitives [US1 foundation]

- [ ] T005 [P] [JR] [WEB] Tests first in `shared/ui/hud/__tests__/`: `Glyph` renders the four kinds plus `hot` with an accessible label; `Meter` sets `aria-valuetext` and 12 ticks; `Dots` prints "N/M"; `DotMatrix` renders a dot set for every character the prototype uses (`A–Z`, `0–9`, `·:-` space) and a `title`; `Decode` and `CountUp` render final text immediately when `reducedMotion`; `Module` renders `h2.lbl`, renders `index` only when passed, applies `tone` classes.
- [ ] T006 [JR] [WEB] Move `Glyph`, `Spark`, `Decode`, `Corners`, `Module`, `Meter`, `Dots`, `CountUp` from `pages/jarvis/hud/Frame.tsx` and `DotMatrix` from `pages/jarvis/hud/DotMatrix.tsx` into `shared/ui/hud/<Name>.tsx`, one per file; export from `shared/ui/index.ts`. Do not touch `pages/jarvis/**` (T017 re-points it and deletes its copies, so the build stays green in between). T005 passes.
- [ ] T007 [JR] [WEB] Add `shared/ui/hud/{Control,CommandChip,Chip}.tsx` per plan.md (`.ctl`, `.ctl.cmd`, `.chip` / `.chip.solid` / `.chip.dotted`), each with a test: 44 px min size class present, `aria-pressed`/`aria-current` forwarded, `CommandChip` renders index, label and key hint.

## Phase 3: Presence [US3]

- [ ] T008 [ENG] [WEB] Test first `entities/presence/model/presence.test.ts`: table over (state, event) → state for every event in FR-006, including `ws_closed` from any state → `error` with phrase "Offline", `ws_open` from `error` → `idle`, `turn_thinking("Looking at your calendar")` → `thinking` with that phrase, `turn_token` → `speaking`, `turn_message` → `done` then `idle` after 1 s (fake timers), `turn_message` from `idle` → stays `idle`, `ask_focus` + `ask_text(true)` → `listening`, `ask_blur` → `idle` unless a turn is in flight, `turn_error` → `idle` with no phrase. Then `usePresence.test.tsx` calling `usePresence("t1")` with `useWsStore.setState` and a fake frame emitter: a replayed message after `ws_open` leaves the orb `idle`; thinking and tokens for thread `t2` are ignored; a token with `thread_id: null` is ignored; thinking for `t1` → `thinking`; a token for `t1` → `speaking`; `usePresence(null)` derives no turn events. Implement `nextPresence` and `usePresence(activeThreadId)` (plan.md `entities/presence`); no import from `entities/session` inside `entities/presence`.
- [ ] T009 [ENG] [WEB] Copy `Orb.tsx`, `LeaderLine.tsx`, `noise.ts` to `shared/ui/hud/presence/` and write `Presence.tsx` there with props `state`, `phrase`, `compact` (session clock included); export from `shared/ui/index.ts`. Orb reads palette colours from computed root styles and observes `data-palette`. Pause on `IntersectionObserver` off-screen and on `document.hidden`. Tests: `heartbeat()` periodicity (2.2 s) and the stagger bound (≤ 320 ms at r = 1); with reduced motion mocked, `requestAnimationFrame` is called at most once (spy); `Presence` sets `aria-live="polite"` only for `attention`, `done`, `error`. Do not touch `pages/jarvis/**` (T017).

- [ ] T009a [ENG] [WEB] Test first `shared/ui/hud/presence/gaze.test.ts`: the US7 independent-test timeline (follow and clamp, peer after `PEER_DELAY_MS`, lose interest within the attention span range, return to centre, startle above `STARTLE_SPEED` once, blink on a target switch beyond `SWITCH_DISTANCE` once, doze after `DOZE_AFTER_MS`, wake on input, `glance(point)`, touch glance then return, neutral output when the orb state is not `idle`). Implement `gaze.ts` with `GAZE_PERSONALITY`.
- [ ] T009b [ENG] [WEB] Wire the gaze into `Orb.tsx` per plan.md (window listeners into a ref, rAF read, spring with overshoot, parallax core shift, lean, blink, startle, doze; `glance` via `useImperativeHandle`; disabled under reduced motion; paused off-screen/hidden). Tests: no React re-render on 100 synthetic `pointermove` events (render counter), reduced motion registers no gaze listeners, non-idle state ignores pointer input. The shell calls `glance` on a `notification` frame (bell element) and when the overlay opens (T013/T012). Record a capture of a pointer sweep, peer, flick, doze and wake (US7 acceptance) in T019.

## Phase 4: Shell, Ask bar, routes [US1, US2, US4]

- [ ] T010 [ENG] [WEB] Test first `shared/config/places.test.ts`: five places in order; `placeOf()` for every new path including detail paths; every redirect row of FR-011 maps old → new with params; `goalPath`, `workflowPath(id, executionId?)`, `askPath(threadId?)`, `settingsDataPath()` (→ `/governance/settings#your-data`). Implement `shared/config/places.ts`. Delete `shared/config/nav-routes.ts` and its test; update every importer from plan.md "Blast radius" in the same change. Then the link audit (FR-014): `git grep -nE 'navigate\(|to=|href=' -- apps/ze-web/src`, fix every old-path literal and every `navigate("/")` meaning chat (→ `askPath()`), excluding `pages/jarvis/**` (T017); list the sites you changed in the Handoffs note. Then `notificationHref(n)` (FR-014a) in `widgets/app-shell/lib/notification-format.ts` from the 184 target table, with one test per target type (`target_parent_id` optional), and `NotificationBell` using it.
- [ ] T011 [ENG] [WEB] Test first `features/ask-bar/ui/AskBar.test.tsx` and `model/ask-overlay.test.ts`: submit on `/doing/goals/g1` opens the overlay and queues `{ text, context: { screen: "doing.goals", goal_id: "g1" } }` without navigating; `askAbout` opens the overlay prefilled and queues nothing; `close` state; `resolve-screen` table for every place and detail route; disabled with accessible name containing "Ze is offline" when presence `offline`; mic control disabled with label "Voice input arrives later"; `/` focuses the input except inside inputs/textareas; dispatches `ask_focus`/`ask_blur`/`ask_text`. Implement `features/ask-bar` (move `resolve-screen.ts` from `features/open-context-overlay/model/`, re-key on `placeOf`; `ask-overlay.ts`; `askAbout`).
- [ ] T012 [ENG] [WEB] Test first `widgets/chat-workspace/ui/AskOverlay.test.tsx` (US6 independent test and acceptance 1–4): one `message` frame per outbox item on `useSession().threadId` with its context, location unchanged, streamed reply and components render, "Open in Ask" → `/ask/<thread>`, "New chat" calls `newSession()` and the next frame uses the new id, Esc closes, stays open across navigation, hidden on `/ask`. Implement `AskOverlay` per plan.md, export it, and pass it from `app/router` as `AppShell`'s `overlay`. Delete `ContextOverlay.tsx` (+ test) and `features/open-context-overlay` (incl. the `ze_overlay_thread_id` key); remove `FloatingButton` from `GoalsOverview`, `WorkflowsOverview`, `CostsOverview` (+ test), `PluginScreen` (+ test); change `WorkflowDetailPage` `openForExecution` to `askAbout({ text, context: { screen: "doing.workflows", workflow_id, execution_id } })` (+ test: overlay opens prefilled).
- [ ] T013 [ENG] [WEB] Test first `widgets/app-shell/ui/AppShell.test.tsx` (rewrite): five tabs with `aria-current` on the active place; strip shows the legend and a clock with an accessible date; Presence renders in the left rail; Ask bar present except on `/ask`; the `overlay` prop renders; `NotificationBell` present; connection dot has an accessible name ("Connected" / "Offline"); phone mock: tabs hidden, bottom bar with five labelled links each carrying the `ctl` class (44 px contract), Ask bar before the bottom bar in DOM order. Implement the shell per plan.md. Delete `NavGroup.tsx` (+ test), `ChatNavGroup.tsx`, the sidebar and old mobile nav, and the Cmd-K handler (keep the `overlay` prop); delete `mergeMobileNavRoutes` from `entities/ui-manifest` (+ its test if any) and its export.
- [ ] T014 [ENG] [WEB] Test first `app/router/routes.test.tsx` with `createMemoryRouter` (e.g. `initialEntries: ["/settings?x=1#your-data"]` → location `/governance/settings?x=1#your-data`): every place path renders inside the shell; every FR-011 redirect preserves `:param`, `?query` and `#hash` (element `RedirectTo` + `<Navigate>`, never a loader); `ask/:threadId` passes the thread to `ChatWorkspace`; `/jarvis` renders as a child of the shell; an unknown non-plugin path renders `RouteErrorPage` in the shell with a "Back to the world" command chip; a manifest plugin path renders `PluginPage`; `/jarvis` still renders. Implement `app/router/{routes.ts,index.tsx}` per plan.md Router.
- [ ] T015 [P] [JR] [WEB] Create `pages/{world,ask,doing,mind,governance}/` with `ui/<Place>Interim.tsx` and `index.ts` per FR-012 (section switcher of `Control` tabs; lazy old pages; first section is the index). Test per place: the switcher lists the FR-012 sections and the active section follows the URL.

## Phase 5: Palette in Governance [US5]

- [ ] T016 [P] [JR] [WEB] Test first, then `features/choose-palette`: three `Control` buttons (`aria-pressed`) using `shared/lib/palette.ts` from T002 (`applyPalette` + `storePalette`); storage throwing → Orchid, no crash. Render it at the top of Governance › Settings (in `GovernanceInterim`). Do not edit `app/**` or `main.tsx` (T002 owns the bootstrap).

## Phase 6: Jarvis reference cleanup

- [ ] T017 [JR] [WEB] `pages/jarvis` (the only task that edits it): re-point every import to `@/shared/ui` (hud primitives and `presence/`) and `@/shared/lib`; delete `pages/jarvis/hud/{Frame,DotMatrix,Orb,Presence,LeaderLine}.tsx`, `noise.ts` and `jarvis.css`; `JarvisApp` renders its two views in the shell hero (the route is a shell child since T014); `JarvisShell` loses its top bar, strip, Ask form and proto group and keeps only the provider fields listed in the spec's `/jarvis` edge case; prototype links (`model/world.ts`, `hud/Cards.tsx`) use the `places.ts` helpers. `/jarvis` and `/jarvis/assemble` render with no console errors.

## Phase 7: Polish and gates [ENG]

- [ ] T018 [ENG] [WEB] Reduced-motion and keyboard pass: tab order top bar → presence → hero → Ask bar → bottom bar; focus ring per DESIGN.md on every control; `/` shortcut; no `requestAnimationFrame` loop under reduced motion (SC-006).
- [ ] T019 [ENG] [WEB] Captures at 1440×900 and 390×844 of `/`, `/ask`, `/doing`, `/doing/goals/<seeded id>`, `/mind`, `/governance`, `/governance/settings` on `make dev-full` with seed data: zero console errors, `scrollWidth ≤ innerWidth`, every interactive element ≥ 44×44 (script the check in the capture run), plus a recorded clip of the idle orb's curious-pet behaviour (US7). Run the impeccable detector on `shared/ui/hud`, `widgets/app-shell`, `features/ask-bar` (0 findings) and an impeccable critique of the shell (≥ T001 baseline). Attach results to the Handoffs note.
- [ ] T020 [ENG] [PLATFORM] Gates: `make test-web`, `make typecheck-web`, `make web-build`, `cd apps/ze-web && bun run lint`. Record command, result and commit in the Handoffs note.

## Phase 8: Docs [DOCS]

- [ ] T021 [P] [DOCS] `docs/frontend.md`: shell, five places, `shared/styles/ze.css`, `shared/ui/hud`, presence states and their signals, redirect table, interim places and which phase replaces each. Follow the `doc-style` skill.
- [ ] T022 [P] [DOCS] `apps/ze-web/README.md` (routes, `DESIGN.md` pointer); `docs/native-interface.md` (floating launcher removed; the Ask bar opens the contextual overlay, which sends on the thread selected in Ask with `context.screen` and route ids; the exchange is an ordinary Ask thread); `DESIGN.md` Navigation section (five places, phone bottom bar, no prototype group).
- [ ] T023 [DOCS] `AGENTS.md`: Learned Workspace Facts line on web nav groups → five places; phase table row 183; `specs/README.md` index row 183. Set this spec's status to Implemented only after T020 passes.
- [ ] T024 [DOCS] Coverage check: `git diff main...HEAD --stat`; every changed public surface (routes, shell, tokens path) is reflected in the docs above; list any gap in the Handoffs note.

---

## Dependencies

- T001 → everything. T002–T003 → all UI tasks. T004 → T005–T009.
- T005 → T006 → T007. T008 → T009 → T009a → T009b.
- T010 → T011 → T012 (T012 also needs T013's shell for the overlay slot; write AskOverlay against the prop and integrate after T013); T008 → T011; T009 + T011 → T013; T010 → T015; T013 + T015 → T014.
- T016 after T015. T017 after T006, T009, T013. T018–T020 after T017. Docs after T020 (T021–T022 may draft earlier).

## Parallel examples

- T004 ∥ T005 (different files).
- T015 ∥ T013 (pages vs widget); T014 waits for both.
- T021 ∥ T022.

## Lanes

### Lane ENG (Claude Sonnet, lane lead)

Tasks: T001–T003, T008–T009b, T010–T014, T018–T020. Owns `app/**`, `main.tsx`, `public/fonts/**`, `shared/styles/**`, `shared/config/**`, `shared/lib/palette.ts`, `shared/ui/hud/presence/**`, `entities/presence/**`, `features/ask-bar/**`, `widgets/app-shell/**`, `widgets/chat-workspace/**` (`AskOverlay` and the `ContextOverlay` deletion only), the interim-page edits listed in T012, and this phase's `tasks.md`.

### Lane JR (OpenCode junior)

Tasks: T004–T007, T015–T017. Owns `shared/lib/use-*.ts`, `shared/ui/hud/**` except `presence/`, `shared/ui/index.ts` (ENG adds the presence exports in T009), `pages/{world,ask,doing,mind,governance}/**`, `features/choose-palette/**`, `pages/jarvis/**`.

### Docs (Docs Steward)

Tasks: T021–T024. `AGENTS.md`, `specs/README.md` and `docs/native-interface.md` are also edited by phase 184's docs lane: do both floors' docs in one Docs Steward pass in the merge order the Maestro sets. Owns `docs/frontend.md`, `docs/native-interface.md`, `apps/ze-web/README.md`, `DESIGN.md` (Navigation section only), `AGENTS.md`, `specs/README.md`, this spec's status line.
