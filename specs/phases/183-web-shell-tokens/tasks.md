# Tasks: Web Shell and Tokens (W1)

**Input**: [spec.md](./spec.md), [plan.md](./plan.md), `DESIGN.md`, `apps/ze-web/.impeccable/plan/overhaul-plan.md`, reference build `apps/ze-web/src/pages/jarvis/`.

**Build gate**: the user answers OQ-1 and OQ-2 in spec Clarifications (the tasks follow the recommendations; if the user picks otherwise, the Spec Architect amends Phase 4 before it starts). The Spec Architect (Lintel) stays on call.

**Tests**: required (constitution V). **Fail-first**: write the test, run it, see it fail for the stated reason, then implement. Vitest + Testing Library; `matchMedia` mocks for phone (`(max-width: 1023px)`) and reduced motion; `createMemoryRouter` for routes; `useWsStore.setState` and a fake frame emitter for WS signals.

**Lanes**: `[ENG]` Claude Sonnet lane lead (owns shared files, integration and gates). `[JR]` OpenCode junior (exact files given). Floor Reviewer reviews per user story.

**Tags**: `[WEB]` ze-web · `[PLATFORM]` build/config · `[DOCS]` docs and specs. No `[BACKEND]` task in this phase.

**Rules for the implementer**
- FSD: `pages → widgets → features → entities → shared`; run `bun run lint` (boundaries) before each commit.
- Pre-v1 hard cut: delete what FR-015 lists in the same change that replaces it; no re-export shims for moved files (update importers).
- DESIGN.md wins over `jarvis.css` where they disagree; report each disagreement you resolve in the floor Handoffs note.
- No new Tailwind classes in the shell, `shared/ui/hud`, `widgets/presence`, `features/ask-bar`; use `ze.css` classes.
- Every `localStorage` access in try/catch.
- Shared worktree: `git add <your paths>`; `git commit -m ... -- <paths>`. Never `git add -A` or `git stash`. Commit only when the ENG lead or Maestro asks; split commits by user story.

---

## Phase 0: Gate [ENG]

- [ ] T001 [ENG] [WEB] Rebase onto `main`. Record in the Handoffs note: (a) `rtk proxy grep -rln "open-context-overlay\|ContextOverlay\|FloatingButton\|nav-routes\|getRoute\|settingsDataPath\|mergeMobileNavRoutes" apps/ze-web/src` compared with plan.md "Blast radius"; (b) whether `ChatWorkspace` can select a thread from a route param (decides the `ask/:threadId` mapping in plan.md Router); (c) a baseline impeccable critique score of `/jarvis` (SC-004) and captures of `/jarvis` at 1440 and 390. Stop and report any difference to the Spec Architect.

## Phase 1: Tokens and type (blocks everything)

- [ ] T002 [ENG] [WEB] Create `apps/ze-web/src/shared/styles/ze.css` from `pages/jarvis/jarvis.css` per plan.md "Tokens": `:root` scope, palette selectors on `:root[data-palette]`, drop `.proto*`, `.orb-ctl`, `.swatch`, `.sw-name`. Import it from `app/styles/globals.css`.
- [ ] T003 [ENG] [WEB] `app/styles/globals.css`: replace the Space Grotesk import with Saira 200/300/400, Michroma, JetBrains Mono 300/400; remap the `@theme` colour/font/radius variables onto the new tokens (FR-003); delete Inter/Space Grotesk references. Verify: `rtk proxy grep -rn "Space Grotesk\|Inter'" apps/ze-web/src` is empty.
- [ ] T004 [P] [JR] [WEB] Move `useReducedMotion` and `useNarrow` from `pages/jarvis/JarvisShell.tsx` to `shared/lib/use-reduced-motion.ts` and `shared/lib/use-narrow.ts` with tests (media-query change updates the value); export from `shared/lib/index.ts`.

## Phase 2: Shared HUD primitives [US1 foundation]

- [ ] T005 [P] [JR] [WEB] Tests first in `shared/ui/hud/__tests__/`: `Glyph` renders the four kinds plus `hot` with an accessible label; `Meter` sets `aria-valuetext` and 12 ticks; `Dots` prints "N/M"; `DotMatrix` renders a dot set for every character the prototype uses (`A–Z`, `0–9`, `·:-` space) and a `title`; `Decode` and `CountUp` render final text immediately when `reducedMotion`; `Module` renders `h2.lbl`, renders `index` only when passed, applies `tone` classes.
- [ ] T006 [JR] [WEB] Move `Glyph`, `Spark`, `Decode`, `Corners`, `Module`, `Meter`, `Dots`, `CountUp` from `pages/jarvis/hud/Frame.tsx` and `DotMatrix` from `pages/jarvis/hud/DotMatrix.tsx` into `shared/ui/hud/<Name>.tsx`, one per file; export from `shared/ui/index.ts`. Delete `pages/jarvis/hud/Frame.tsx` and `DotMatrix.tsx`; update `pages/jarvis/**` importers. T005 passes.
- [ ] T007 [JR] [WEB] Add `shared/ui/hud/{Control,CommandChip,Chip}.tsx` per plan.md (`.ctl`, `.ctl.cmd`, `.chip` / `.chip.solid` / `.chip.dotted`), each with a test: 44 px min size class present, `aria-pressed`/`aria-current` forwarded, `CommandChip` renders index, label and key hint.

## Phase 3: Presence [US3]

- [ ] T008 [ENG] [WEB] Test first `entities/presence/model/presence.test.ts`: table over (state, event) → state for every event in FR-006, including `ws_closed` from any state → `error` with phrase "Offline", `ws_open` from `error` → `idle`, `typing("Looking at your calendar")` → `thinking` with that phrase, `token` → `speaking`, `message` → `done` then `idle` after 1 s (fake timers), `ask_focus` + `ask_text(true)` → `listening`, `ask_blur` → `idle` unless a turn is in flight, `turn_error` → `idle` with no phrase. Then implement `nextPresence` and `usePresence` (plan.md `entities/presence`).
- [ ] T009 [ENG] [WEB] Move `Orb.tsx`, `LeaderLine.tsx`, `noise.ts` to `widgets/presence/ui/` and `Presence.tsx` with props `state`, `phrase`, `compact` (session clock included). Orb reads palette colours from computed root styles and observes `data-palette`. Pause on `IntersectionObserver` off-screen and on `document.hidden`. Tests: `heartbeat()` periodicity (2.2 s) and the stagger bound (≤ 320 ms at r = 1); with reduced motion mocked, `requestAnimationFrame` is called at most once (spy); `Presence` sets `aria-live="polite"` only for `attention`, `done`, `error`. Delete the moved files from `pages/jarvis/hud/` and re-point jarvis importers (the jarvis World view passes its own phrase).

## Phase 4: Shell, Ask bar, routes [US1, US2, US4]

- [ ] T010 [ENG] [WEB] Test first `shared/config/places.test.ts`: five places in order; `placeOf()` for every new path including detail paths; every redirect row of FR-011 maps old → new with params. Implement `shared/config/places.ts` (places, `placeOf`, `redirects`). Delete `shared/config/nav-routes.ts` and its test; update every importer from plan.md "Blast radius" in the same change (TopBar label lookups, `notification-format.ts` builds new paths per FR-014, `settingsDataPath` → `/governance/settings#your-data`, data features, DataOverview, costs popovers).
- [ ] T011 [ENG] [WEB] Test first `features/ask-bar/ui/AskBar.test.tsx`: submit on `/doing/goals` sets `pendingAsk` with `context.screen` from `resolve-screen` and navigates to `/ask`; disabled with accessible name containing "Ze is offline" when presence `offline`; mic control disabled with label "Voice input arrives later"; `/` focuses the input except inside inputs/textareas; dispatches `ask_focus`/`ask_blur`/`ask_text`. Implement `features/ask-bar` (move `resolve-screen.ts` from `features/open-context-overlay/model/`, re-key on `placeOf`; `pending-ask.ts`; `askAbout`).
- [ ] T012 [ENG] [WEB] `widgets/chat-workspace`: consume `pendingAsk` once on mount through the existing send path on the active thread, then clear it (test: a pending ask is sent exactly once with its `context`). Delete `widgets/chat-workspace/ui/ContextOverlay.tsx` (+ test) and its export; delete `features/open-context-overlay`; remove `FloatingButton` from `GoalsOverview`, `WorkflowsOverview`, `CostsOverview` (+ test), `PluginScreen` (+ test); change `WorkflowDetailPage` `openForExecution` to `askAbout({ text, context: { screen: "workflow", workflow_id, execution_id } })` (+ test).
- [ ] T013 [ENG] [WEB] Test first `widgets/app-shell/ui/AppShell.test.tsx` (rewrite): five tabs with `aria-current` on the active place; strip shows the legend and a clock with an accessible date; Presence renders in the left rail; Ask bar present except on `/ask`; `NotificationBell` present; connection dot has an accessible name ("Connected" / "Offline"); phone mock: tabs hidden, bottom bar with five labelled links, Ask bar before the bottom bar in DOM order. Implement the shell per plan.md. Delete `NavGroup.tsx` (+ test), `ChatNavGroup.tsx`, the sidebar and old mobile nav, the `overlay` prop and Cmd-K handler; delete `mergeMobileNavRoutes` from `entities/ui-manifest` (+ its test if any) and its export.
- [ ] T014 [ENG] [WEB] Test first `app/router/routes.test.tsx`: every place path renders inside the shell; every FR-011 redirect preserves `:param`, `?query` and `#hash`; an unknown non-plugin path renders `RouteErrorPage` in the shell with a "Back to the world" command chip; a manifest plugin path renders `PluginPage`; `/jarvis` still renders. Implement `app/router/{routes.ts,index.tsx}` per plan.md Router.
- [ ] T015 [P] [JR] [WEB] Create `pages/{world,ask,doing,mind,governance}/` with `ui/<Place>Interim.tsx` and `index.ts` per FR-012 (section switcher of `Control` tabs; lazy old pages; first section is the index). Test per place: the switcher lists the FR-012 sections and the active section follows the URL.

## Phase 5: Palette in Governance [US5]

- [ ] T016 [P] [JR] [WEB] Test first, then `features/choose-palette`: three `Control` buttons (`aria-pressed`), writes `document.documentElement.dataset.palette` and `ze.palette`; reads it on app start in `app/App.tsx` before first paint (default `orchid`); storage throwing → Orchid, no crash. Render it at the top of Governance › Settings (in `GovernanceInterim`).

## Phase 6: Jarvis reference cleanup

- [ ] T017 [JR] [WEB] `pages/jarvis`: delete `jarvis.css`; `JarvisApp` renders its two views inside the real `AppShell` hero (no `JarvisShell` chrome: delete the prototype top bar, strip, Ask form and the proto group; keep the context provider fields the views still read, sourcing palette from the root and orb from `usePresence` unless a view sets it). `/jarvis` and `/jarvis/assemble` still render with no console errors.

## Phase 7: Polish and gates [ENG]

- [ ] T018 [ENG] [WEB] Reduced-motion and keyboard pass: tab order top bar → presence → hero → Ask bar → bottom bar; focus ring per DESIGN.md on every control; `/` shortcut; no `requestAnimationFrame` loop under reduced motion (SC-006).
- [ ] T019 [ENG] [WEB] Captures at 1440×900 and 390×844 of `/`, `/ask`, `/doing`, `/doing/goals/<seeded id>`, `/mind`, `/governance`, `/governance/settings` on `make dev-full` with seed data: zero console errors, `scrollWidth ≤ innerWidth`, every interactive element ≥ 44×44 (script the check in the capture run). Run the impeccable detector on `shared/ui/hud`, `widgets/app-shell`, `widgets/presence`, `features/ask-bar` (0 findings) and an impeccable critique of the shell (≥ T001 baseline). Attach results to the Handoffs note.
- [ ] T020 [ENG] [PLATFORM] Gates: `make test-web`, `make typecheck-web`, `make web-build`, `cd apps/ze-web && bun run lint`. Record command, result and commit in the Handoffs note.

## Phase 8: Docs [DOCS]

- [ ] T021 [P] [DOCS] `docs/frontend.md`: shell, five places, `shared/styles/ze.css`, `shared/ui/hud`, presence states and their signals, redirect table, interim places and which phase replaces each. Follow the `doc-style` skill.
- [ ] T022 [P] [DOCS] `apps/ze-web/README.md` (routes, `DESIGN.md` pointer); `docs/native-interface.md` (contextual overlay removed; Ask bar sends `context.screen`; workflow detail sends `workflow_id`/`execution_id`); `DESIGN.md` Navigation section (five places, phone bottom bar, no prototype group).
- [ ] T023 [DOCS] `AGENTS.md`: Learned Workspace Facts line on web nav groups → five places; phase table row 183; `specs/README.md` index row 183. Set this spec's status to Implemented only after T020 passes.
- [ ] T024 [DOCS] Coverage check: `git diff main...HEAD --stat`; every changed public surface (routes, shell, tokens path) is reflected in the docs above; list any gap in the Handoffs note.

---

## Dependencies

- T001 → everything. T002–T003 → all UI tasks. T004 → T005–T009.
- T005 → T006 → T007. T008 → T009 → T013.
- T010 → T011 → T012; T010 → T013 → T014; T015 needs T010 and runs beside T013.
- T016 after T015. T017 after T006, T009, T013. T018–T020 after T017. Docs after T020 (T021–T022 may draft earlier).

## Parallel examples

- T004 ∥ T005 (different files).
- T015 ∥ T013 (pages vs widget), both after T010.
- T021 ∥ T022.

## Lanes

### Lane ENG (Claude Sonnet, lane lead)

Tasks: T001–T003, T008–T014, T018–T020. Owns `app/**`, `shared/styles/**`, `shared/config/**`, `entities/presence/**`, `features/ask-bar/**`, `widgets/app-shell/**`, `widgets/presence/**`, `widgets/chat-workspace/**` (pending-ask consumer and overlay deletion only), the interim-page edits listed in T012, and this phase's `tasks.md`.

### Lane JR (OpenCode junior)

Tasks: T004–T007, T015–T017. Owns `shared/lib/use-*.ts`, `shared/ui/hud/**`, `shared/ui/index.ts`, `pages/{world,ask,doing,mind,governance}/**`, `features/choose-palette/**`, `pages/jarvis/**`.

### Docs (Docs Steward)

Tasks: T021–T024. Owns `docs/frontend.md`, `docs/native-interface.md`, `apps/ze-web/README.md`, `DESIGN.md` (Navigation section only), `AGENTS.md`, `specs/README.md`, this spec's status line.
