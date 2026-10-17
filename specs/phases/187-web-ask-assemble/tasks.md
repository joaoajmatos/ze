# Tasks: Ask / Assemble (W3)

**Input**: [spec.md](./spec.md), [plan.md](./plan.md), DESIGN.md.

**Build gate**: start when 184, 195 and 186 are on `main`. The Spec Architect (Lintel) stays on call for design questions.

**Tests**: required (constitution V). **Fail-first**: write the test, run it, see it fail for the stated reason, then implement. Vitest + Testing Library; the reducer is tested as a pure function over frame sequences; WS frames are injected through the existing test helper for `useFrame`.

**Lanes**: `[ENG]` Claude Sonnet lane lead (conversation store and reducer, turn-stream handler, canvas, overlay, page, gates). `[JR]` OpenCode junior (exact files given). Floor Reviewer reviews per user story. `[DOCS]` Docs Steward.

**Tags**: `[WEB]` ze-web and `@myguyze/ze-ui` · `[DOCS]` docs and specs.

**Rules for the implementer**
- FSD: `pages → widgets → features → entities → shared`; no same-layer cross-slice imports. `widgets/assemble` reaches the overlay through `AppShell`'s `overlay` prop from `app/router` (no widget-to-widget import). Callbacks (`onChatAbout`) go down by props.
- Every chat frame is handled once: the conversation reducer owns `typing`, `token`, `message`, `edit`, `error`, `message_superseded`, `message_rollback`; `confirm_*` stay with the pending-confirmation store, `trace_update` with the trace store, `refresh`/`notification` with invalidation. No other `useFrame` for those seven.
- No client composition of presets (SC-002). No new primitive types (spec Clarifications).
- DESIGN.md tokens; reduced motion = opacity-only cascade; 44 px targets.
- Before changing a shared export, run `graphify affected "<Symbol>" --depth 2` and `rtk proxy grep -rn "<symbol>" apps/ze-web/src packages/ze-ui/src`; update every caller in the same change.
- Shared worktree: `git add <paths>`; `git commit -m ... -- <paths>`; never `git add -A` or `git stash`. Commit only when the ENG lead or Maestro asks; split commits by user story.

---

## Phase 0: Gate [ENG]

- [ ] T001 [ENG] [WEB] Branch from `main` with 184, 195 and 186 merged. `make web-install`; `graphify update .` (the graph at plan time predated 183), then `graphify affected` on `useChatWorkspace`, `ChatWorkspace`, `AskOverlay`, `useMessages`, `useRetryReply`, `useTraceStore`, `ConnectedPrimitiveTree`, `PrimitiveRenderer`, `useConfirmation`, `Spotlight`, and grep `usePresence`, `useFrame(`, `ChatShell`, `compose.ts`, `Ze's Mind`. Record in the Handoffs note: (a) differences from plan.md "Blast radius"; (b) where 195 put the single send path (`useChatWorkspace.sendMessage` or a helper) and its `screenSnapshot` signature; (c) where 186's `features/answer-gate` listens for `error` frames (it must read the conversation store after T004, not its own `useFrame`); (d) every `useFrame` call for the seven conversation frames; (e) the impeccable baseline critique of the 183/195 interim Ask. Stop and report differences to the Spec Architect.

## Phase 1: Conversation store and reducer [US1, US4, US5]

- [ ] T002 [ENG] [WEB] Tests first `entities/conversation/model/reducer.test.ts`, a table of frame sequences: typing → token × n → message (phase awaiting → thinking → speaking → idle; streaming text accumulates and clears); a frame for another thread updates only that thread; an untagged `error` affects only a thread that is awaiting/thinking/speaking; `error` code `busy` → `lastOutcome busy`; retry error codes → their outcomes with the plan; `edit` patches text and components; `message_superseded` marks and swaps; `message_rollback` sets `rollback` on the message; `sent` adds the optimistic user line (resend keeps the original); `delivery_failed` sets `failed`; `history_loaded` merges by id and keeps order. Implement `model/reducer.ts`, `model/store.ts`, selectors, `index.ts`.
- [ ] T003 [ENG] [WEB] Move `features/load-chat-history/api/useMessages.ts` to `entities/conversation/api/useThreadHistory.ts` writing `history_loaded` (+ test: load, reload returns the new history, thread change resets); delete `features/load-chat-history`.

## Phase 2: Turn stream [US1, US2]

- [ ] T004 [ENG] [WEB] Tests first `features/turn-stream/ui/TurnFrameHandler.test.tsx`: each of the seven frames reaches the reducer once (spy); `ack` sent for an unread assistant reply of the active thread only; presence events dispatched for the active thread only; sessions invalidated (debounced) on typing and assistant messages; `onboarding` meta updates `useOnboardingSession`. Implement `TurnFrameHandler.tsx`; mount it in `widgets/app-shell/ui/AppShell.tsx` beside the other handlers. Remove the four `useFrame` handlers from `entities/presence/model/usePresence.ts` (presence gets the same events from the handler) and update its tests. Point 186's `features/answer-gate` error detection at the store (T001(c)).
- [ ] T005 [ENG] [WEB] Tests first `features/turn-stream/model/watchdog.test.ts` (fake timers): 120 s of silence → history reload → `delivery_failed` when no new reply; activity resets the timer; an interrupted thread is checked on reconnect. Implement `model/watchdog.ts`, run from the handler.
- [ ] T006 [ENG] [WEB] Tests first `features/turn-stream/api/useSendTurn.test.ts`: the frame carries `{ ...screenSnapshot(), ...explicitContext, workspace_placed }` (195 shape); `origin` resets after the first send; a preset passes `compose`/`topic` and `origin: "preset"`; offline returns false with the notice; `sent` reaches the reducer. Implement; move 195's send path here and delete the old one.
- [ ] T007 [ENG] [WEB] SC-001 test `features/turn-stream/frame-coverage.test.ts`: for every member of `WsInboundFrame`, exactly one slice subscribes (scan of `useFrame(` call sites via a registry the handlers export, not a text grep).

## Phase 3: Renderer restyle [US2]

- [ ] T008 [ENG] [WEB] Tests first in `packages/ze-ui/src/react/PrimitiveRenderer.test.tsx`: with a `classNames` map in context, atoms render the mapped classes (text variants heading/label/muted, badge, progress, card-style `col`, table, steps, connections, button); without a map the defaults remain (plugin hosts); `headline` uses the `renderHeadline` slot when given; `claim_card` and `claim_timeline` render the HUD layout. Implement in `PrimitiveRenderer.tsx` and `context.tsx`; README section.
- [ ] T009 [JR] [WEB] `apps/ze-web/src/features/primitive-tree`: pass the ze.css `classNames` map and `renderHeadline` (`DotMatrix`) through `ConnectedPrimitiveTree` (+ test); plugin screens pick it up unchanged.

## Phase 4: Assemble widget [US1–US6]

- [ ] T010 [ENG] [WEB] Tests first `widgets/assemble/ui/Canvas.test.tsx`: a reply renders the Sentence module then one `Module` per top-level component in order with `A·NN` indexes; spans by type on desktop, all 12 when `compact`; tone from the component's `claim`; streaming text while speaking; disclosure line under the first reply; pin moves a module to the top, dismiss hides it (view state); a preset reply renders `headline`, `claim_timeline`, `claim_card`s in order; `assembling` dispatched during the cascade and cleared after; reduced motion → no transform. Implement `Canvas.tsx` and the cascade (origin = `.presence-orb` bounding box).
- [ ] T011 [ENG] [WEB] Tests first `widgets/assemble/ui/TraceModule.test.tsx`: each section renders from a trace fixture (Routing with `preset`/`open_query`/tier, Memory relevance, Tools gate/effect, Skills, Judgments, Sources, Workspace, Conductor, Confirmations, Rollback, Feedback thumbs in the head, Screen with "Asked from/about" and resolver statuses); phone collapses behind one chip. Port the sections from `chat-workspace/ui/trace-panel/*` into `widgets/assemble/ui/trace/*`.
- [ ] T012 [P] [JR] [WEB] Tests first `widgets/assemble/lib/why.test.ts`: preset reply → Routing; rendered module → Tools with `render_*`/`show_*` rows highlighted; no trace → link hidden. Implement `lib/why.ts` and `ui/WhyLink.tsx`.
- [ ] T013 [ENG] [WEB] Tests first `widgets/assemble/ui/ConfirmationPlacement.test.tsx`: write confirmation with an editable body round-trips approve with edits and deny; budget and held render their titles and source; prompt shows actions as command chips sending `action`; `confirm_cancel` closes it; only the given thread's confirmations show. Implement (wraps `ConfirmationCard`).
- [ ] T014 [ENG] [WEB] Tests first `widgets/assemble/ui/RetryControl.test.tsx`: shown on the latest reply only; two-step plan consent sends `retry` with `confirmed_plan`; `message_rollback` updates the rollback section; `message_superseded` swaps the reply; disabled with its reason when history is unavailable; notices from `lastOutcome`. Remove the frame subscriptions from `features/retry-reply/model/useRetryReply.ts` (it reads the store) and update its tests.
- [ ] T015 [ENG] [WEB] Tests first `widgets/assemble/ui/AskOverlay.test.tsx` (moved from `widgets/chat-workspace`): 183/195 behaviour kept (thread = selected session, outbox, New chat, Open in Ask, chat-about subject); a reply with components renders as `Canvas compact`; a `write` confirmation for the overlay thread renders inside the overlay; Retry on the latest reply; "Open in Ask" shows the same thread with the same modules (shared store). Implement; update `app/router/routes.tsx` to import `AskOverlay` from `widgets/assemble`.
- [ ] T016 [JR] [WEB] Tests first: the canvas publishes `canvas` refs (`index`, `type`, `ref` from `claim`) and `focused_module` (`useScreenPublisher` mock); every module with a `claim` shows `ChatAboutChip` calling the passed `onChatAbout` with that ref (195 FR-025). Implement in `Canvas.tsx` after T010 merges.

## Phase 5: Rails and page [US1, US2, US6, US7]

- [ ] T017 [P] [JR] [WEB] Tests first `widgets/sessions-rail/ui/SessionsRail.test.tsx`: list, search, thinking/attention dots, select sets the session, New chat. Port from `chat-workspace/ui/SessionList.tsx`.
- [ ] T018 [P] [JR] [WEB] Tests first `widgets/try-chips/ui/TryChips.test.tsx`: three chips with the right `compose`/`topic`; the goal chip uses the top goal in the snapshot and is hidden without one; keys 1–3 only when the Ask bar is empty and unfocused; each calls the passed `onSend`. Implement.
- [ ] T019 [ENG] [WEB] Tests first `pages/ask/ui/AskPage.test.tsx`: desktop layout (rail, canvas, trace module for the selected reply) and phone order; the Ask bar sends directly on `/ask` through `useSendTurn`; `ask/:threadId` selects that thread; an onboarding `message` frame selects `onboarding:<session_id>` when no turn is running, and Presence shows "getting to know you" until `completed`; `busy` outcome shows "Ze is still working on the last one" with Cancel (`command: cancel`). Implement `AskPage.tsx`, `pages/ask/index.ts`, route.

## Phase 6: Hard cuts [US2]

- [ ] T020 [ENG] [WEB] Delete `widgets/chat-workspace/**`, `features/chat-side-panel`, `pages/chat`, `pages/ask/ui/AskInterim.tsx` (+ tests), `shared/ui/layout/ChatShell.tsx` (+ export). Replace "Ze's Mind" strings with "trace". `rtk proxy grep -rn "chat-workspace\|chat-side-panel\|load-chat-history\|AskInterim\|ChatShell\|Ze's Mind" apps/ze-web/src` empty.
- [ ] T021 [JR] [WEB] Remove `Spotlight` from `widgets/onboarding-wizard/ui/OnboardingWizard.tsx` (ze.css background; test still passes); delete `shared/effects/{background-beams,glowing-stars,spotlight}.tsx` and any export.
- [ ] T022 [JR] [WEB] Delete `pages/jarvis/model/compose.ts`, `pages/jarvis/views/AssembleView.tsx` and its route in `JarvisApp.tsx`; move the `Component` type into `pages/jarvis/hud/Cards.tsx`. SC-002: `rtk proxy grep -rn "model/compose\|AssembleView\|composeAnswer" apps/ze-web/src` empty.

## Phase 7: Acceptance [ENG]

- [ ] T023 [ENG] [WEB] Gates: `make test-web`, `make typecheck-web`, `make web-build`, `make lint`. Impeccable critique of Ask ≥ 29/40 and ≥ the T001 baseline; detector 0 on touched slices; captures at 1440 and 390 with no console errors; reduced-motion capture shows opacity-only cascade. Against `make dev`: a full turn, a preset ("What's slipping?"), a write confirmation in `/ask` and in the overlay, a Retry with undo. Record in the Handoffs note.

## Phase 8: Docs [DOCS]

- [ ] T024 [DOCS] Update every doc in plan.md "Docs touched".
- [ ] T025 [DOCS] `AGENTS.md` phase row 187 and the chat-chrome preference line; `specs/README.md` row 187 → Implemented; spec status.
- [ ] T026 [DOCS] Coverage check: `git diff main...HEAD --stat` against "Docs touched"; record in the Handoffs note.

---

## Dependencies

- T001 before everything.
- T002 → T003, T004; T004 → T005, T007; T002 → T006.
- T008 → T009. T010 needs T002, T009. T011, T012 independent after T002. T013 after T002. T014 after T002, T004. T015 after T010, T013, T014. T016 after T010.
- T017, T018 independent after T002. T019 after T006, T010, T011, T017, T018.
- T020 after T015 and T019. T021, T022 independent.
- T023 after all code; T024–T026 last.

## Parallel examples

- After T001: ENG takes T002 then T004; JR takes T012 (after T002), T017, T018, T021, T022.
- After T008: JR takes T009 while ENG builds T010.

## Lanes

### Lane ENG (Claude Sonnet, lane lead)

T001–T008, T010, T011, T013–T015, T019, T020, T023. Owns `app/router/*`, `widgets/app-shell/ui/AppShell.tsx`, `entities/presence`.

### Lane JR (OpenCode junior)

T009, T012, T016–T018, T021, T022.

### Docs (Docs Steward)

T024–T026.

### Cross-lane touch points

- `widgets/assemble/ui/Canvas.tsx`: T010 (ENG) then T016 (JR).
- `features/primitive-tree/ui/ConnectedPrimitiveTree.tsx`: T009 (JR) only; T010 consumes it.
- `packages/ze-ui/src/react/*`: T008 (ENG) only.
