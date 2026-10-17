# Tasks: Ask / Assemble (W3)

**Input**: [spec.md](./spec.md), [plan.md](./plan.md), DESIGN.md.

**Build gate**: start when 184, 195 and 186 are on `main`. The Spec Architect (Lintel) stays on call for design questions.

**Tests**: required (constitution V). **Fail-first**: write the test, run it, see it fail for the stated reason, then implement. Vitest + Testing Library; the reducer is tested as a pure function over frame sequences; WS frames are injected through the existing test helper for `useFrame`.

**Lanes**: `[ENG]` Claude Sonnet lane lead (conversation store and reducer, turn-stream handler, canvas, overlay, page, gates). `[JR]` OpenCode junior (exact files given). Floor Reviewer reviews per user story. `[DOCS]` Docs Steward.

**Tags**: `[WEB]` ze-web and `@myguyze/ze-ui` · `[DOCS]` docs and specs.

**Rules for the implementer**
- FSD: `pages → widgets → features → entities → shared`; no same-layer cross-slice imports. `widgets/assemble` reaches the overlay through `AppShell`'s `overlay` prop from `app/router` (no widget-to-widget import). Callbacks (`onChatAbout`) go down by props.
- One state owner per frame: the conversation reducer owns `typing`, `token`, `message`, `edit`, `error`, `message_superseded`, `message_rollback`; `confirm_*` stay with the pending-confirmation store, `trace_update` with the trace store, `refresh`/`notification` with invalidation. Any other `useFrame` is a listener registered in `features/turn-stream/frame-registry.ts` with a reason, and never writes the conversation store.
- FSD: `features/turn-stream` imports only entities and shared; `features/ask-bar` stays prop-driven (`onSubmit`); `AppShell`, `AskOverlay` and `pages/ask` wire one to the other.
- No client composition of presets (SC-002). No new primitive types (spec Clarifications).
- Trace instruments draw only what `MessageTrace` and `trace_update` carry (Clarifications 2026-10-18): no threshold line, no main-model cost or context meter, no tool overlap, no duration or success from live partial tool frames. Coral is never used in the trace (nothing in it has slipped).
- DESIGN.md tokens; reduced motion = opacity-only cascade; 44 px targets.
- Before changing a shared export, run `graphify affected "<Symbol>" --depth 2` and `rtk proxy grep -rn "<symbol>" apps/ze-web/src packages/ze-ui/src`; update every caller in the same change.
- Shared worktree: `git add <paths>`; `git commit -m ... -- <paths>`; never `git add -A` or `git stash`. Commit only when the ENG lead or Maestro asks; split commits by user story.

---

## Phase 0: Gate [ENG]

- [ ] T001 [ENG] [WEB] Branch from `main` with 184, 195 and 186 merged. `make web-install`; `graphify update .` (the graph at plan time predated 183), then `graphify affected` on `useChatWorkspace`, `ChatWorkspace`, `AskOverlay`, `useMessages`, `useRetryReply`, `useTraceStore`, `ConnectedPrimitiveTree`, `PrimitiveRenderer`, `useConfirmation`, `Spotlight`, and grep `usePresence`, `useFrame(`, `ChatShell`, `compose.ts`, `Ze's Mind`. Record in the Handoffs note: (a) differences from plan.md "Blast radius"; (b) where 195 put the single send path (`useChatWorkspace.sendMessage` or a helper) and its `screenSnapshot` signature; (c) where 186's `features/answer-gate` listens for `error` frames (it must read the conversation store after T004, not its own `useFrame`); (d) every `useFrame` call for the seven conversation frames; (e) the impeccable baseline critique of the 183/195 interim Ask. Stop and report differences to the Spec Architect.

## Phase 1: Conversation store and reducer [US1, US4, US5]

- [ ] T002 [ENG] [WEB] Tests first `entities/conversation/model/reducer.test.ts`, a table of frame sequences: typing → token × n → message (phase awaiting → thinking → speaking → idle; streaming text accumulates and clears); a frame for another thread updates only that thread; an untagged `error` affects only a thread that is awaiting/thinking/speaking; `error` code `busy` → `lastOutcome busy`; retry error codes → their outcomes with the plan; `edit` patches text and components; `message_superseded` marks and swaps; `message_rollback` sets `rollback` on the message; `sent` adds the optimistic user line and records `lastSent.at` (the Signal path's zero; resend keeps the original); `delivery_failed` sets `failed`; `history_loaded` merges by id and keeps order; `typing` moves awaiting → thinking; `paused` applies only to a thread that is awaiting, thinking or speaking (a prompt-kind confirmation on an idle thread, e.g. a goal gate, does not pause) and `resumed` restarts the clock; an assistant message on a non-active thread sets `attention` and `opened` clears it; any tagged message sets `lastMessageAt` and any tagged error sets `lastError` even on an idle thread. Implement `model/reducer.ts`, `model/store.ts`, selectors, `index.ts`.
- [ ] T003 [ENG] [WEB] Move `features/load-chat-history/api/useMessages.ts` to `entities/conversation/api/useThreadHistory.ts` writing `history_loaded` (+ test: load, reload returns the new history, thread change resets, loaded unread assistant messages are acked); delete `features/load-chat-history`.

## Phase 2: Turn stream [US1, US2]

- [ ] T004 [ENG] [WEB] Tests first `features/turn-stream/ui/TurnFrameHandler.test.tsx`: each of the seven frames reaches the reducer once (spy); `confirm_request` for a busy thread dispatches `paused`; `useConfirmation.respond` dispatches `resumed` only after approve or deny of a non-held confirmation (a prompt answered with an action does not, matching `useConfirmation.ts` today); held confirmations (no thread) dispatch neither; `useWsStore` thinking/typing/attention flags follow the store (sessions rail dots); `ack` sent for an unread assistant reply of the active thread only; presence events dispatched for the active thread only; sessions invalidated (debounced) on typing and assistant messages; `onboarding` meta updates `useOnboardingSession`. Implement `TurnFrameHandler.tsx`; mount it in `widgets/app-shell/ui/AppShell.tsx` beside the other handlers. Remove the four `useFrame` handlers from `entities/presence/model/usePresence.ts` (presence gets the same events from the handler) and update its tests. Point 186's `features/answer-gate` error detection at the store (T001(c)).
- [ ] T005 [ENG] [WEB] Tests first `features/turn-stream/model/watchdog.test.ts` (fake timers): 120 s of silence → history reload → `delivery_failed` when no new reply; activity resets the timer; a confirmation open for 10 minutes never fails the turn and approving it restarts the timer; an interrupted thread is checked on reconnect. Implement `model/watchdog.ts`, run from the handler.
- [ ] T006 [ENG] [WEB] Tests first `features/turn-stream/api/useSendTurn.test.ts`: `send(threadId, text, { explicitContext, workspacePlaced, origin })` produces `{ ...screenSnapshot(), ...explicitContext, workspace_placed }` (195 shape) with no import from `features/ask-bar` (lint); `origin` resets after the first send; a preset passes `compose`/`topic` and `origin: "preset"`; offline returns false with the notice; `sent` reaches the reducer. Implement; move 195's send path here and delete the old one.
- [ ] T007 [ENG] [WEB] SC-001 test `features/turn-stream/frame-coverage.test.ts`: every member of `WsInboundFrame` has exactly one `state-owner` entry in `frame-registry.ts`, or an explicit `none` owner for frames with no client state (`pong`); every other `useFrame` call site is a registered `listener` with a reason (`ConfirmationFrameHandler` ack, `RefreshHandler`, `AppShell` glance, `TurnFrameHandler` on `confirm_*`); a listener calling a conversation-store setter fails the test.

## Phase 3: Renderer restyle [US2]

- [ ] T008 [ENG] [WEB] Tests first in `packages/ze-ui/src/react/PrimitiveRenderer.test.tsx`: with a `classNames` map in context, atoms render the mapped classes (text variants heading/label/muted, badge, progress, card-style `col`, table, steps, connections, button); without a map the defaults remain (plugin hosts); `headline` uses the `renderHeadline` slot when given; `claim_card` and `claim_timeline` render the HUD layout. Implement in `PrimitiveRenderer.tsx` and `context.tsx`; README section.
- [ ] T009 [JR] [WEB] `apps/ze-web/src/features/primitive-tree`: pass the ze.css `classNames` map and `renderHeadline` (`DotMatrix`) through `ConnectedPrimitiveTree` (+ test); plugin screens pick it up unchanged.

## Phase 4: Assemble widget [US1–US6]

- [ ] T010 [ENG] [WEB] Tests first `widgets/assemble/ui/Canvas.test.tsx`: a reply renders the Sentence module then one `Module` per top-level component in order with `A·NN` indexes; an assistant message with no preceding user line (proactive, gate reply, recap, onboarding) is its own exchange with the "Ze, unprompted" label; a `failed` turn shows `DeliveryFailedRow` whose Resend resends `lastSent` (context and attachments) without a second user line; the latest reply has compact thumbs; spans by type on desktop, all 12 when `compact`; tone from the component's `claim`; streaming text while speaking; disclosure line under the first reply; pin moves a module to the top, dismiss hides it (view state); a preset reply renders `headline`, `claim_timeline`, `claim_card`s in order; `assembling` dispatched during the cascade and cleared after; reduced motion → no transform. Implement `Canvas.tsx` and the cascade (origin = `.presence-orb` bounding box).
- [ ] T011 [ENG] [WEB] Tests first `widgets/assemble/ui/TraceModule.test.tsx`: the rail for the selected reply. The head has "trace", the feedback thumbs and the coordinate readout ("Asked from · …" / "Asked about · …" from `screen`). The body has the Signal path slot, then one collapsed line per instrument, each with its main readout, expanding on hover, focus or click (keyboard: Enter toggles, `aria-expanded`). Then the readout rows, ported from `chat-workspace/ui/trace-panel/*` into `widgets/assemble/ui/trace/rows/*` with their existing tests: Skills, Sources, Workspace, Conductor, Confirmations, Screen resolver statuses. `TraceSheet` puts the same rail in the HUD `Dialog` (overlay "Why?" and phone). Instruments render as placeholders until T027–T033 land.
- [ ] T012 [P] [JR] [WEB] Tests first `widgets/assemble/lib/why.test.ts`: preset reply → Routing; rendered module → Tools with `render_*`/`show_*` rows highlighted; no trace → link hidden. Implement `lib/why.ts` and `ui/WhyLink.tsx`.
- [ ] T013 [ENG] [WEB] Tests first `widgets/assemble/ui/ConfirmationPlacement.test.tsx`: write confirmation with an editable body round-trips approve with edits and deny; budget and held render their titles and source; prompt shows actions as command chips sending `action`; `confirm_cancel` closes it; only the given thread's confirmations show. Implement (wraps `ConfirmationCard`).
- [ ] T014 [ENG] [WEB] Tests first `widgets/assemble/ui/RetryControl.test.tsx`: shown on the latest reply only; two-step plan consent sends `retry` with `confirmed_plan`; `message_rollback` updates the rollback section; `message_superseded` swaps the reply; disabled with its reason when history is unavailable; notices from `lastOutcome`. Remove the frame subscriptions from `features/retry-reply/model/useRetryReply.ts` (it reads the store) and update its tests.
- [ ] T015 [ENG] [WEB] Tests first `widgets/assemble/ui/AskOverlay.test.tsx` (moved from `widgets/chat-workspace`): 183/195 behaviour kept (thread = selected session, outbox, New chat, Open in Ask, chat-about subject); a reply with components renders as `Canvas compact`; a `write` confirmation for the overlay thread renders inside the overlay; Retry on the latest reply; "Open in Ask" shows the same thread with the same modules (shared store). The outbox carries `workspacePlaced`; the overlay sends it with `useSendTurn` passing the outbox context. Implement; update `app/router/routes.tsx` to import `AskOverlay` from `widgets/assemble`.
- [ ] T016 [JR] [WEB] Tests first: the canvas publishes `canvas` refs (`index`, `type`, `ref` from `claim`) and `focused_module` (`useScreenPublisher` mock); every module with a `claim` shows `ChatAboutChip` calling the passed `onChatAbout` with that ref (195 FR-025). Implement in `Canvas.tsx` after T010 merges.

## Phase 4b: Trace instruments [US8]

Pure layout functions first, then views. Fixtures: one rich finished trace (compound routing, routing and tier judgments, intake rows with an `intake_outcome`, five memory chunks with one null confidence, tool calls across two agents with an irreversible approved write and a denied one, a compaction, rollback entries), one partial sequence, and one history trace with no arrivals.

- [ ] T027 [ENG] [WEB] Tests first `features/trace-state/model/useTraceStore.test.ts` (extend): `mergePartialTrace` stamps the client arrival time once per stage (route, screen, memory, tier, tool n), keyed by which fields the partial carries; `commitPendingTrace` moves the stamps to `arrivalsByMessage[message_id]` and clears the pending ones; hydrated traces have no arrivals; a second turn on the thread starts fresh; a retry, or a turn refused as busy, never stamps the previous turn's pending trace (arrivals are keyed by the committed reply's `message_id`). Implement in `useTraceStore.ts`.
- [ ] T028 [P] [JR] [WEB] Tests first `widgets/assemble/lib/instruments/signal.test.ts`: stages are returned in pipeline order (screen, route, memory, tier, tools), each with its own "+x.x s" offset from `sentAt`; screen only when `screen` is set; memory only when chunks arrived (with the count); tier only when `tier` is set; a single-agent turn with no `model_simple` and no memory returns screen/route/tools only, and no "waiting" stage is ever returned; while streaming the reply is the pending end; a history trace returns every drawn stage settled with `total_duration_ms` and no offsets; preprocess, skills, correlate, surface, synthesize and memory write are never returned. Implement `signal.ts`.
- [ ] T029 [P] [JR] [WEB] Tests first `lib/instruments/routing.test.ts` and `lib/instruments/judgments.test.ts`. Routing (Gauge T-1), one test row per method: `embedding` with no `agent` judgment, or one not consumed, → "E5 score" with ghost `confidence − score_gap` clamped at 0; `embedding` with `agent` consumed → "Choice confidence", no ghost; `screen`, `preset`, `forced`, `open_query` → "fixed", no bar, no ghost; `haiku` → no ghost; `fallback` → no bar; method words for every method; routing-judgment options sorted by probability with the answer marked; tier line from `tier`; the coordinate readout for `ask_bar`, `chat_about` and missing `screen`. Judgments: the closed question-id map (`agent` and `multi_specialist` → routing; `routing` is not an id) groups rows by surface (unknown → humanised id); `intake_outcome` is handled before the Choice renderer (no probabilities); Choice, Noul and Score shapes; consumed versus skipped with the reason in words; `intake_outcome` parsed from `<kind>:<reason>[:<link>]` into words for all seven `OutcomeKind` values (`persist_fact`, `resolve_loop`, `create_loop_declared`, `create_loop_suspected`, `link`, `hold`, `fallback`; unknown → humanised) and the link kind; `hold:forget_not_created` reads as words through the humanise fallback. Implement both.
- [ ] T030 [P] [JR] [WEB] Tests first `lib/instruments/memory.test.ts`, `tools.test.ts` and `readouts.test.ts`. Memory: points from the committed trace only, x = score, y = extraction confidence (null → floor), glyph by source, ranked list order. Tools (Gauge T-3): lanes by agent (null agent → the reply's agent, listed first); x = cumulative earlier durations within the same lane only (a fixture where a `delegate_to_agent` call and its delegate's calls would exceed `total_duration_ms` if summed across lanes: no lane uses another lane's time); the delegate call carries "includes the delegate's calls"; minimum width for 0 ms; irreversible, per-call `gate` and failure marks; no write-confirmation ticks; partial calls have no width and read "returned". Readouts (Gauge T-2): "System One: N requests, X ms, Y input tokens" counts one request per surface group. A fixture with a six-row intake group, plus `intake_outcome`, plus one routing row gives 2 requests and their two latencies, not 8. Also: total, model or "not recorded", compaction span, resume recap, and no money anywhere. Implement all three.
- [ ] T031 [ENG] [WEB] Tests first `widgets/assemble/ui/trace/SignalPath.test.tsx`: the strip starts at the origin point; one tick per stage from `signal.ts` with its arrival readout; the newest lit tick carries `data-live` while streaming; the settled strip shows the total in `DotMatrix`; reduced motion (mocked `matchMedia`) renders no sweep element. Implement; wire into `TraceModule` (live from the pending trace while the thread's turn is streaming).
- [ ] T032 [ENG] [WEB] Tests first `RoutingInstrument.test.tsx` and `JudgmentGauges.test.tsx`: the confidence bar plus the runner-up ghost with values as text; needles per option with the chosen one cream; the tier line; the coordinate readout; no threshold element rendered (asserted). Gauges grouped by surface with skip reasons in words and the intake decision line. Implement both.
- [ ] T033 [ENG] [WEB] Tests first `MemoryConstellation.test.tsx`, `ToolsTimeline.test.tsx`, `Readouts.test.tsx` and `ReversalTrack.test.tsx`. Constellation: rendered from the committed trace only (while streaming it is absent and the Signal path shows the chunk count); one mark per chunk; hover and focus show the text; arrow keys move focus; phone (`useMediaQuery` mocked) renders the ranked list. Tools: lanes on separate axes, the caption "order and duration per lane; start times not recorded", the delegate note, irreversible and gate marks with text labels, a streaming call reading "returned". Readouts: the dot-matrix total, model, System One line, compaction mark. Reversal track: entries in reverse order with outcomes in words. No coral class anywhere in the trace. Implement all four.

## Phase 5: Rails, Ask bar and page [US1, US2, US6, US7]

- [ ] T016a [ENG] [WEB] Tests first `features/ask-bar/ui/AskBar.test.tsx` and `widgets/app-shell/ui/AppShell.test.tsx`: the bar renders on every place including `/ask`; it is prop-driven (`onSubmit(text, explicitContext, workspacePlaced)`); the paperclip calls `placeWorkspaceFile`, shows a chip per placed file, shows "Could not place the file in the workspace." on failure, sends the chips' `{path,size}` as `workspacePlaced` and clears them after a successful submit; `AppShell` wires `onSubmit` to `useSendTurn` on `/ask` and to the overlay outbox elsewhere (`OutboxItem.workspacePlaced`). Implement in `features/ask-bar` and `AppShell.tsx`.

- [ ] T034 [ENG] [WEB] Tests first `shared/api/ws-client.test.ts` (extend), `entities/presence/model/usePresence.test.ts`, `widgets/app-shell/ui/AppShell.test.tsx` and the connection-dot test: `takeOver()` clears `displaced` and connects even when the document is hidden; `useConnectionState()` returns `online`, `displaced` or `offline`; while displaced, `usePresence` dispatches nothing (orb idle, no "Offline"), the connection dot reads "Open in another window", every place shows "Ze is open in another window" with "Use here" (calls `takeOver`; tested on a visible, unfocused window, since focus already takes over), the Ask bar is disabled with that reason (`disabledReason` prop), and World's and the overlay's "Ze is offline" wording switches to the displaced line; after takeover the line goes. Implement `takeOver`, `useConnectionState`, `widgets/app-shell/ui/DisplacedNotice.tsx`, the Ask bar prop, and the `entities/presence` change (ENG-owned).

- [ ] T017 [P] [JR] [WEB] Tests first `widgets/sessions-rail/ui/SessionsRail.test.tsx`: list, search, thinking/attention dots, select sets the session, New chat. Port from `chat-workspace/ui/SessionList.tsx`.
- [ ] T018 [P] [JR] [WEB] Tests first `widgets/try-chips/ui/TryChips.test.tsx`: three chips with the right `compose`/`topic`; the goal chip uses the active goal with the latest `last_progress_at`, falling back to `created_at` when it is null (test a new goal), and is hidden without one; keys 1–3 only when the Ask bar is empty and unfocused; each calls the passed `onSend`. Implement.
- [ ] T019 [ENG] [WEB] Tests first `pages/ask/ui/AskPage.test.tsx`: desktop layout (rail, canvas, trace module for the selected reply) and phone order; on `/ask` the bar's `onSubmit` sends on the selected thread through `useSendTurn`; `ask/:threadId` selects that thread; an onboarding frame selects `onboarding:<session_id>` once per session id, not again on a reconnect re-send, never when the URL names a thread or the bar has text (the rail shows "Continue getting to know you" instead), and Presence shows "getting to know you" until `completed`; `busy` outcome shows "Ze is still working on the last one" with Cancel (`command: cancel`). Implement `AskPage.tsx`, `pages/ask/index.ts`, route.

## Phase 6: Hard cuts [US2]

- [ ] T020 [ENG] [WEB] Delete `widgets/chat-workspace/**`, `features/chat-side-panel`, `pages/chat`, `pages/ask/ui/AskInterim.tsx` (+ tests), `shared/ui/layout/ChatShell.tsx` (+ export). Replace "Ze's Mind" strings with "trace". `rtk proxy grep -rn "chat-workspace\|chat-side-panel\|load-chat-history\|AskInterim\|ChatShell\|Ze's Mind" apps/ze-web/src` empty.
- [ ] T021 [JR] [WEB] Remove `Spotlight` from `widgets/onboarding-wizard/ui/OnboardingWizard.tsx` (ze.css background; test still passes); delete `shared/effects/{background-beams,glowing-stars,spotlight}.tsx` and any export.
- [ ] T022 [JR] [WEB] Delete `pages/jarvis/model/compose.ts`, `pages/jarvis/views/AssembleView.tsx` and its route in `JarvisApp.tsx`; move the `Component` type into `pages/jarvis/hud/Cards.tsx`. SC-002: `rtk proxy grep -rn "model/compose\|AssembleView\|composeAnswer" apps/ze-web/src` empty.

## Phase 7: Acceptance [ENG]

- [ ] T023 [ENG] [WEB] Gates: `make test-web`, `make typecheck-web`, `make web-build`, `make lint`. Impeccable critique of Ask ≥ 29/40 and ≥ the T001 baseline; detector 0 on touched slices; captures at 1440 and 390 with no console errors; reduced-motion capture shows opacity-only cascade. Against `make dev`: a full turn (the Signal path lights live and settles), a preset ("What's slipping?"), a write confirmation in `/ask` and in the overlay, a Retry with undo (reversal track), a second window ("Use here"). Captures of the trace rail at 1440 and of the "Why?" sheet at 390. Record in the Handoffs note.

## Phase 8: Docs [DOCS]

- [ ] T024 [DOCS] Update every doc in plan.md "Docs touched".
- [ ] T025 [DOCS] `AGENTS.md` phase row 187 and the chat-chrome preference line; `specs/README.md` row 187 → Implemented; spec status.
- [ ] T026 [DOCS] Coverage check: `git diff main...HEAD --stat` against "Docs touched"; record in the Handoffs note.

---

## Dependencies

- T001 before everything.
- T002 → T003, T004; T004 → T005, T007; T002 → T006.
- T008 → T009. T010 needs T002, T009. T011, T012 independent after T002. T013 after T002. T014 after T002, T004. T015 after T010, T013, T014. T016 after T010.
- T017, T018 independent after T002. T016a after T006. T019 after T006, T010, T011, T016a, T017, T018. T020 (deletes `ChatInput`) after T016a.
- T020 after T015 and T019. T021, T022 independent.
- T027 after T002. T028–T030 independent after T001 (fixtures first). T031 after T011, T027, T028. T032 after T011, T029. T033 after T011, T030. T034 independent after T016a.
- T023 after all code; T024–T026 last.

## Parallel examples

- After T001: ENG takes T002 then T004; JR takes T012 (after T002), T017, T018, T021, T022.
- After T008: JR takes T009 while ENG builds T010.
- After T001: JR takes T028–T030 (pure instrument layouts) alongside its other lane work; ENG wires views T031–T033 once T011 lands.

## Lanes

### Lane ENG (Claude Sonnet, lane lead)

T001–T008, T010, T011, T013–T015, T016a, T019, T020, T023, T027, T031–T034. Owns `app/router/*`, `widgets/app-shell/ui/AppShell.tsx`, `entities/presence`.

### Lane JR (OpenCode junior)

T009, T012, T016–T018, T021, T022, T028–T030.

### Docs (Docs Steward)

T024–T026.

### Cross-lane touch points

- `widgets/assemble/ui/Canvas.tsx`: T010 (ENG) then T016 (JR).
- `features/primitive-tree/ui/ConnectedPrimitiveTree.tsx`: T009 (JR) only; T010 consumes it.
- `packages/ze-ui/src/react/*`: T008 (ENG) only.
- `widgets/assemble/ui/TraceModule.tsx`: T011 (ENG), then T031–T033 (ENG) wire instruments in.
- `widgets/assemble/lib/instruments/*`: T028–T030 (JR) only; views import them.

### Size

With US8 the phase has 34 code tasks. That is still one floor: the instrument layouts are pure functions in the JR lane, and the ENG views follow the canvas. If the floor lead finds it too big at T001, split Phase 4b (T027–T033) into a follow-up floor that starts after T011. It touches only `widgets/assemble/ui/trace/*`, `lib/instruments/*` and the trace store.
