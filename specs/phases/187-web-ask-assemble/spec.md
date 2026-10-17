# Feature Specification: Ask / Assemble (W3)

**Feature Branch**: `187-web-ask-assemble`

**Created**: 2026-10-17

**Status**: Ready to implement once 184, 195 and 186 are on `main` (plan and tasks written 2026-10-17 against `main` b9e62e7b)

**Input**: Maestro brief 2026-10-17, phase W3; overhaul plan sections a (Ask), b.2, c (how the conversation works), e (Phase W3). User decision 7: "B1 runs before W3; W3 does not ship client-side compositions"; decision 9: instrument ids only on the Assemble canvas.

**Governed by**: `DESIGN.md` (canvas, cascade from the orb, trace terminology), `PRODUCT.md` ("Every reply has a trace"), phase 117 (static AI disclosure, chat always resolves), 165/180 (feedback, retry, rollback), 181 (write confirmations, `kind` write/budget/held/prompt), 51 (onboarding).

**Depends on**: 183 (shell), 184 (composed answers, claim descriptors), 195 (screen context, "Chat about this", `MessageTrace.screen`), 186 (loop/goal/decision module visuals shared with World).

**Doctrine functions served**: perception (the user's input), reflection (the trace), governance (confirmations, retry with undo).

---

## Clarifications

### Session 2026-10-17 (planning against the code)

Binding for the plan.

- **There are no `metric`, `timeline`, `list`, `card_notice`, `choice_group`, `confirm`, `review`, `consent`, `connect_account` or `progress_steps` primitives on the wire.** The `render_*` tools build those patterns from atoms (`col`, `row`, `text`, `badge`, `divider`, `spacer`, `button`, `progress`, `table`, `form`, `connections`, `steps`, `chart`) plus 184's `headline`, `claim_card`, `claim_timeline`. The HUD look comes from restyling those atoms (text variants, badge, card-style `col`) in `@myguyze/ze-ui`; no new renderer types are added.
- **One conversation store, one reducer.** Today every `useChatWorkspace` instance keeps its own messages and parses frames, so the overlay and `/ask` do not share a thread's state. A per-thread store (`entities/conversation`) with a pure reducer owns `typing`, `token`, `message`, `edit`, `error`, `message_superseded` and `message_rollback`. One handler mounted in the shell feeds it and dispatches the presence events. `confirm_request`/`confirm_cancel` stay with the pending-confirmation store (one handler already), `trace_update` with the trace store, `refresh`/`notification` with invalidation. SC-001 means exactly this split, with no frame handled twice.
- **"Why?" cannot name the exact tool call yet.** Message components carry no call index (`ToolCallTrace.call_index` exists; components do not point at it). "Why?" opens the reply's trace module at the section for the module's origin: Routing for a preset reply (`method: preset`), Tools (render and show rows highlighted) otherwise. The per-module link is a backend gap recorded for 194 (a `source_call_index` on top-level components).
- **Onboarding starts on the server.** On connect, `start_if_needed` sends the onboarding view as a `message` frame on thread `onboarding:<session_id>` with `OnboardingMeta { session_id, completed }` (no step data). Ask opens that thread when the frame arrives and no other turn is running, and Presence shows "getting to know you" until `completed`. No stepper: the meta has no steps to draw. The `onboarding` command is not sent by the client.
- **`pages/chat` is unrouted dead code** (183 removed its route); it is deleted with `widgets/chat-workspace`. `shared/effects/spotlight.tsx` is used by `widgets/onboarding-wizard` (first-run configuration); the wizard switches to the ze.css background in this phase so the effects can go.
- **Deleting the `/jarvis` composition** removes `pages/jarvis/model/compose.ts`, `views/AssembleView.tsx` and its `/jarvis` sub-route; the `Component` type `hud/Cards.tsx` imports moves into `Cards.tsx`. The rest of `/jarvis` stays until 193.

## Overview

Ask is where the user talks to Ze, at `/ask` and `/ask/:threadId`. Every reply assembles as HUD modules on a 12-column canvas, flying in from the orb 80 ms apart; the reply text is the Sentence module; the trace is a module beside the answer, one "Why?" away from any module. It replaces the interim Ask section (the old chat page), the trace side panel, the session list in the nav, the confirmation card, retry and the old onboarding chat entry. It also gives the contextual overlay from phase 183 the same assembly: the user decided (2026-10-17, 183 OQ-2) that the Ask bar on any other screen opens an overlay where the answer arrives in place, and that the exchange is a real Ask thread. Phase 183 built the overlay shell and thread behaviour; this phase renders the overlay's replies with the same canvas, trace chip, confirmation card and Retry as `/ask`.

## Modules

- **Contextual overlay** (every place except `/ask`): the 183 `AskOverlay` shell (thread = the session selected in Ask, `context.screen` per message, "Open in Ask", "New chat") now renders each reply as the Assemble canvas in compact form (spans collapse to 12, instrument index kept), with the cascade from the Presence orb's position, the trace behind a chip per reply, the confirmation card in place for the overlay thread, and Retry on the latest reply.

- **Left rail**: Presence (orb phases driven by the turn: listening → thinking on `typing` with `typing.text` as the phrase → speaking on first `token` → done on `message`; `assembling` while components cascade; "getting to know you" during onboarding), **Try** chips (keys 1–3): "What's slipping?" (`context.compose="slipping"`), "What should I decide today?" (`decisions`), "How is <top goal> going?" (`topic`, topic = the top-ranked goal's title from the priority snapshot), and **Sessions** (history, search: `listSessions`, `searchSessions`).
- **Canvas**: Sentence (tokens stream in; decode on settle), then one module per top-level component: the 184 primitives (`headline` as the dot-matrix headline, `claim_card`, `claim_timeline`) and every existing atom restyled (col, row, text, badge, divider, spacer, button, progress, table, form, connections, steps, chart), which restyles every `render_*` pattern built from them. Instrument index = position in the answer (decision 9). Pin and dismiss per module.
- **Trace module**: routing (agent, method incl. `preset` and `open_query`, confidence, tier), memory used with relevance, tools with gate and effect, skills, judgments, sources, effects known, write confirmations, rollback; feedback thumbs in its head; collapsed behind one chip on phones.
- **Confirmation card**: in place on `confirm_request` (write: one row per item with the imperative effect phrase and an editable body when `editable_field` is set; budget; held with the source run named; prompt: title as the question and actions as command chips); Approve/Deny send `confirm`; prompt buttons send `action`; `confirm_cancel` closes it everywhere. The same component renders in World/Doing Needs you.
- **Retry**: on the latest reply, two-step undo-plan consent (`retry_eligibility`, `confirmed_plan`), `message_rollback` updates the rollback section, `message_superseded` swaps the reply; disabled with its reason when history is unavailable.
- **Onboarding**: the server starts it on connect (thread `onboarding:<session_id>`); Ask opens that thread; Presence says "getting to know you" until `completed`; forms and choices are primitives submitting `component_submit`.

## User Scenarios & Testing *(mandatory)*

1. **A full turn streams with a progressive trace (P1).** Test: WS frame reducer over `typing`, `token`, `trace_update` (partial), `message`, `edit`, `error` (busy → "Ze is still working on the last one" with Cancel); orb phase sequence.
2. **A preset answers with backend modules (P1).** Tapping "What's slipping?" sends `message` with `context.compose`; the canvas renders the reply's `headline`, `claim_timeline`, `claim_card`s in order with posture visuals; no client composition code exists (`rtk proxy grep compose.ts` empty).
3. **"Why?" lands on the trace section for the module's origin (P2).** Test: a preset reply's module opens Routing; a rendered module opens Tools with the render rows highlighted (per-call link deferred to 194).
4. **A write confirmation round-trips (P1)**, incl. editable body and deny; `confirm_cancel` closes it.
5. **Retry with undo (P1)**: plan shown, confirmed, `message_rollback` reflected, reply swapped.
6. **Ask in place (P1).** From `/doing/goals/g1` the Ask bar opens the overlay; the reply assembles there as modules (same component as `/ask`, compact); "Why?" opens its trace chip; a `write` confirmation for that thread renders in the overlay and round-trips; "Open in Ask" shows the same thread with the same modules. Test: overlay renders the canvas for a reply with components; confirmation for the overlay thread renders inside it, not as a separate card.
7. **Phone (P1)**: Presence compact → Try chips → canvas (spans collapse to 12, timeline omitted) → Trace behind a chip.

## Requirements *(mandatory)*

- **FR-001**: `pages/ask` with widgets `assemble` (canvas, trace module, confirmation placement, overlay), `sessions-rail`, `try-chips`; `entities/conversation` (store, reducer, history); `features/turn-stream` (frame handler, single send path, watchdog); `PrimitiveRenderer` in `@myguyze/ze-ui/react` restyled to the system (atoms with ze.css classes, `h2.lbl` labels, meters, chips) and HUD renderers for the 184 primitives (184 added plain ones). The module frame per top-level component is drawn by the canvas, not the renderer.
- **FR-002**: Keep: `features/respond-to-confirmation`, `features/retry-reply` (its frame subscriptions move into the reducer; it keeps the request, the plan consent and the notices), `features/reply-feedback`, `features/trace-state`. Move: `features/load-chat-history` into `entities/conversation/api`.
- **FR-003**: The Ask bar from 183 is shown on `/ask` too (the old chat composer is deleted) and sends directly on the selected thread there; on every other place it keeps opening the overlay (183 FR-008a). The canvas, trace module and confirmation placement live in one slice, `widgets/assemble` (`Canvas`, `TraceModule`, `AskOverlay` moved from `widgets/chat-workspace`), used by `pages/ask` and passed to `AppShell`'s `overlay` prop from `app/router` (no widget-to-widget import).
- **FR-004**: Hard cuts: `widgets/chat-workspace` (AskOverlay moves to `widgets/assemble`; ChatWorkspace, ChatSidePanel, ChatSidePanelQuickActions, MessageBubble, ChatMessageList, SessionList, TypingIndicator, trace-panel as they are), `features/chat-side-panel`, `pages/chat` (unrouted), `pages/ask/ui/AskInterim.tsx`, `features/load-chat-history` (moved), `shared/effects/{background-beams,glowing-stars,spotlight}.tsx` (the starfield; the onboarding wizard stops using `Spotlight`), `pages/jarvis/model/compose.ts`, `pages/jarvis/views/AssembleView.tsx` and its route, `shared/ui/layout/ChatShell.tsx`, any "Ze's Mind" wording.
- **FR-004a**: Screen context (phase 195): Ask publishes the canvas modules (`canvas` refs with index and type) and the focused module; every canvas card and overlay reply module wires "Chat about this" (callbacks passed down by props from widgets, 195 FR-024); the Trace module's head shows "Asked from: …" or "Asked about: …" from `MessageTrace.screen`, and a Screen section lists the resolver rows (ok, missing, stale, cut).
- **FR-005**: The static AI disclosure (phase 117) is kept, restyled, in the Ask rail.
- **FR-006**: Acceptance: impeccable critique ≥ 29/40 on Ask; detector 0; captures; reduced motion cascades are opacity-only.

## Success Criteria *(mandatory)*

- **SC-001**: Every WS frame type the server sends to the chat is handled by one reducer with tests.
- **SC-002**: No client-side composition of presets exists.
- **SC-003**: `make test-web`, `make typecheck-web`, `make web-build`, lint pass.

## Out of Scope

- Voice (193). Backend changes: none. Gap found while planning, for 194: top-level components carry no tool `call_index`, so "Why?" cannot link one module to one call.

## Owning packages

ze-web, `@myguyze/ze-ui`; no backend, no migration.
