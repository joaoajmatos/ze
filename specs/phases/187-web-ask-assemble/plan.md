# Implementation Plan: Ask / Assemble (W3)

**Branch**: `187-web-ask-assemble` | **Date**: 2026-10-17 | **Spec**: [spec.md](./spec.md)

**Input**: spec.md (Clarifications 2026-10-17 and 2026-10-18 are binding; revised after Gauge's review A-1..A-10, then for the user's trace-instruments request and the displaced window on 2026-10-18), `main` at b9e62e7b, 184 floor at 9ca300d8 (claim primitives, preset send, `useCardActions`), the 195 plan (screen-context store, single send path, `chatAbout`), the 186 plan (posture table, Needs-you rows). DESIGN.md "Canvas", "Cascade", "Trace".

## Summary

Ask becomes the Assemble canvas. The core change is structural. Conversation state moves out of the per-instance `useChatWorkspace` hook into one per-thread store (`entities/conversation`) with a pure reducer. One frame handler mounted in the shell feeds it (`features/turn-stream`), so `/ask` and the overlay show the same thread, and every chat frame is parsed once. On top of that store, `widgets/assemble` renders each reply as a Sentence module plus one module per top-level component, cascading from the orb. It shows the trace as a module and places confirmations in place, in both `/ask` and the overlay. `@myguyze/ze-ui` atoms are restyled to the HUD system. The trace is drawn as a rail of HUD instruments (US8) from the data the client already receives, and a window displaced by another shows "Use here". `widgets/chat-workspace`, the side panel, the starfield and the `/jarvis` composition are deleted.

## Technical Context

**Language/Version**: TypeScript 5, React 19, zustand, TanStack Query 5 (ze-web); `@myguyze/ze-ui` (React renderer).
**Primary Dependencies**: none new.
**Storage**: none server-side. Pin/dismiss per module is view state (not persisted).
**Testing**: vitest; the reducer is a pure function with a table of frame sequences; component tests per module; ze-ui renderer tests.
**Constraints**: FSD; DESIGN.md tokens; reduced motion = opacity-only cascade; 44 px targets; no client composition of presets (SC-002); every chat frame handled once (SC-001).
**Scale**: one thread on screen at a time; history pages from `listMessages`.

## Constitution Check

| Principle | Check |
|---|---|
| Spec first | spec.md + Clarifications; plan and tasks here. |
| Honest claims | "Why?" links to the section it can prove (origin), not to a guessed call. Onboarding shows no stepper it cannot fill. Trace "Asked from" comes from `MessageTrace.screen`. |
| Package boundaries | ze-web and `@myguyze/ze-ui` only. One backend gap recorded for 194, not patched here. |
| Pre-v1 hard cuts | `widgets/chat-workspace`, `features/chat-side-panel`, `features/load-chat-history` (moved), `pages/chat`, `AskInterim`, effects, `ChatShell`, `/jarvis` composition, "Ze's Mind" wording deleted in this phase. |
| Tests | Fail-first; reducer table; frame-coverage test for SC-001. |
| Docs are part of done | [DOCS] tasks cover "Docs touched". |

## Blast radius

`graphify affected` on `main` b9e62e7b. The graph predates part of 183 (it still names `ContextOverlay`), so T001 re-runs it after `graphify update .`. Plus `rtk proxy grep`:

| Symbol | Callers | Change |
|---|---|---|
| `useChatWorkspace` | `ChatWorkspace.tsx`, `AskOverlay.tsx` (183), `pages/chat` | Deleted. State → `entities/conversation`; sending → `features/turn-stream` `useSendTurn` (195's single send path moves here; its `screenSnapshot()` merge and `origin` reset move with it). |
| `ChatWorkspace` | `pages/chat` (unrouted), `pages/ask/ui/AskInterim.tsx`, `widgets/chat-workspace/index.ts` | Deleted. |
| `AskOverlay` (grep) | `app/router/routes.tsx` (AppShell `overlay` prop), `widgets/chat-workspace/index.ts`, its test | Moves to `widgets/assemble`; renders `Canvas compact`. |
| `useMessages` | `useChatWorkspace` only | Moves to `entities/conversation/api/useThreadHistory.ts` writing the store. |
| `useRetryReply` | `ChatWorkspace.tsx` | Frame subscriptions removed (the reducer applies `message_superseded`, `message_rollback`, retry `error`); keeps `retry()`, plan consent, notices read from the store's `lastOutcome`. |
| `usePresence` (grep: `entities/presence/model/usePresence.ts`) | `AppShell` presence wiring | Its `useFrame` handlers for `typing`/`token`/`message`/`error` are removed; `features/turn-stream` dispatches the same presence events for the active thread (an entity cannot read another entity). `assembling` is dispatched by the canvas during a cascade. |
| `useTraceStore`, `useSessionTraces`, `useTraceSocket` | chat-workspace side panel, `MessageBubble`, `TraceContent` | Kept; read by `widgets/assemble` `TraceModule`. `mergePartialTrace` also stamps each partial's client arrival time by stage (`pendingArrivals`), moved to `arrivalsByMessage[message_id]` on commit; history traces have none. |
| `chat-workspace/ui/trace-panel/*` (Routing, Memory, Tools, Judgments, Rollback, Skills, Workspace, Conductor, Confirmations, Feedback, TraceContent, TraceEntry) | the side panel, `MessageBubble` | Routing, Memory, Tools, Judgments and Rollback become instruments; the rest are ported as readout rows into `widgets/assemble/ui/trace/`; the folder is deleted with `chat-workspace`. |
| `useWsStore.displaced`, `takeOverIfDisplaced` (`shared/api/ws-client.ts`, f75e6848) | ws-client only | New export `takeOver()` (clears `displaced`, connects now, ignores visibility); read by `AppShell` and the Ask bar. |
| `ConnectedPrimitiveTree` | `MessageBubble`, `ChatMessageList` (deleted), `PluginScreen`, `PluginSettingsSection` | Used by the canvas per top-level component; plugin screens keep using it (they get the restyle too). |
| `PrimitiveRenderer` (ze-ui) | `ConnectedPrimitiveTree`, `usePrimitiveRendererActions`, `usePluginScreenActions`, `PluginScreen`, `PluginSettingsSection` | Restyle only; props unchanged. Plugin screens change look, not behaviour. |
| `useConfirmation`, `ConfirmationCard` | `useChatWorkspace`, `AskOverlay`, `NotificationBell` (186 removes), 186 Needs you | Kept; placed by `widgets/assemble`. |
| `Spotlight` | `OnboardingWizard.tsx` | Removed from the wizard; effects deleted. |
| `compose.ts`, `AssembleView` (`/jarvis`) | `JarvisApp.tsx`, `hud/Cards.tsx` (type import) | Deleted; route removed; type moved into `Cards.tsx`. |
| `AskBar`, `useAskOverlay` (`features/ask-bar`) | `AppShell.tsx` (renders the bar off `/ask` today), `AskOverlay` | Bar shown on every place, prop-driven `onSubmit(text, explicitContext, workspacePlaced)`, attach control and chips; `OutboxItem` gains `workspacePlaced`. |
| `ChatInput` attach (`placeWorkspaceFile`) | `ChatWorkspace.tsx` | Moves to the Ask bar before `chat-workspace` is deleted. |
| "Ze's Mind" (grep) | copy strings | Replaced with "trace". |

## Design

### `entities/conversation`

- `model/store.ts`: `useConversation = create<{ byThread: Record<string, ThreadState> }>` with `ThreadState = { messages: Message[] (ordered by created_at, keyed by id), historyLoaded, turn: { phase: "idle"|"awaiting"|"thinking"|"speaking"|"paused"|"failed", typingText, streamingText, activityAt, lastSent: { text, context, workspacePlaced } | null }, lastOutcome: { kind: "retry_failed"|"retry_partial"|"rolled_back_retry_failed"|"busy"|"error", detail, plan? } | null, lastMessageAt, lastError: { detail, code, at } | null, attention: boolean }`.
- `model/reducer.ts` (pure): `reduce(state, event, now)`. Events: frames `typing`, `token`, `message`, `edit`, `error`, `message_superseded`, `message_rollback`; local `sent`, `history_loaded`, `delivery_failed`, `paused` (a `confirm_request` for the thread: phase `paused`, watchdog stops), `resumed` (the confirmation was answered: phase `awaiting`, watchdog restarts), `opened` (thread became active: clears `attention`), `reset`. Rules ported from `useChatWorkspace`: frames tagged with another thread update that thread; an untagged `error` applies only to a thread in `awaiting`/`thinking`/`speaking`; any tagged `message` sets `lastMessageAt` and any tagged `error` sets `lastError` whatever the phase (186's gate tracking reads both); an assistant `message` on a thread that is not active sets `attention`; `typing` moves `awaiting` → `thinking` (the old `stopThinking` hand-over to the typing indicator); `message` clears the turn and keeps the reply; `token` appends to `streamingText`; `edit` patches text/components; `message_superseded` marks `replaced_by` and swaps; `message_rollback` sets `message.rollback`; `error` with `code` `busy` → `lastOutcome busy` ("Ze is still working on the last one", Cancel), retry codes → the matching outcome. The optimistic user bubble on `sent` (resend keeps the original).
- `api/useThreadHistory.ts`: `listMessages` → `history_loaded`; acks loaded assistant messages with `read: false` (as `useMessages.loadHistory` does); reload for the watchdog.
- Selectors: `useThread(threadId)`, `useTurn(threadId)`, `latestAssistant(threadId)`.

### `features/turn-stream`

- `ui/TurnFrameHandler.tsx`, mounted once in `AppShell` beside `ConfirmationFrameHandler` and `RefreshHandler`: subscribes to the seven frames plus `confirm_request`/`confirm_cancel` (for `paused`; the pending store stays the owner of confirmation state), calls `reduce`, keeps `useWsStore` thinking/typing/attention flags in sync (the sessions rail dots), sends `ack` for unread assistant replies of the active thread, invalidates sessions (debounced) and dispatches presence events (`turn_thinking`, `turn_token`, `turn_message`, `turn_error`) for the active thread only; updates `useOnboardingSession` from `message.onboarding`.
- `useConfirmation.respond` dispatches `resumed` after sending.
- `frame-registry.ts`: every `useFrame` call site registers `{ frame, slice, role: "state-owner" | "listener", reason }`. State owners: conversation (seven frames), pending-confirm store (`confirm_*`), trace store (`trace_update`), invalidation (`refresh`, `notification` cache). Listeners: `ConfirmationFrameHandler` acknowledging on `typing`/`token`/`message`, `RefreshHandler` on `message` (186), `AppShell` glance on `notification`, `TurnFrameHandler` on `confirm_*`.
- `model/watchdog.ts`: one timer per awaiting thread (stopped while `paused`) (`DELIVERY_WATCHDOG_MS` 120 s of silence → reload history → `delivery_failed` if no new reply); reconnect check for interrupted threads (from `useWsStore.interruptedThreads`).
- `api/useSendTurn.ts`: the single send path (195): `send(threadId, text, { explicitContext, workspacePlaced, origin })` → `{ ...screenSnapshot(place, route), ...explicitContext, workspace_placed }`; it imports only entities and shared (FSD: the explicit context is an argument, never read from `features/ask-bar`), `origin` reset after the first send, preset sends (184) and Try chips use it with their `context`, returns false and shows the not-connected notice when offline.
- `model/thinking.ts`: `useWsStore` thinking/typing flags stay the source for other consumers (sessions rail dots); the handler keeps them in sync.

### `widgets/assemble`

- `ui/Canvas.tsx` (`compact` prop for the overlay): exchanges are grouped as a user line plus the assistant messages that follow it; an assistant message with no preceding user line in the thread (proactive message, gate-action reply, resume recap, onboarding view) is its own exchange with an origin label ("Ze, unprompted"); each reply renders as a Sentence module (streaming text while `speaking`; `Decode` on settle; static disclosure line under the first reply of a thread) and one `Module` per top-level component (`index` = `A·NN` by position, decision 9; `tone` from the component's `claim` via the 186 posture table and 184 `claim_tone`), rendered by `ConnectedPrimitiveTree`. Grid: 12 columns desktop with spans by component type (headline 12, claim_card 4, claim_timeline 12, chart 8, table 8, others 6); `compact` and phone collapse to 12. Pin (moves the module to the top of the canvas for this view) and dismiss (hides it for this view). Cascade: modules fly from the orb's bounding box 80 ms apart (`assembling` signal while running); reduced motion = opacity only.
- `ui/TraceModule.tsx`: sections ported from `chat-workspace/ui/trace-panel/*` (Routing incl. `preset`, `open_query`, confidence, tier; Memory with relevance; Tools with gate and effect; Skills; Judgments; Sources; Workspace; Conductor; Confirmations; Rollback; Feedback thumbs in the head) plus Screen (195: "Asked from/about" label in the head; resolver rows ok/missing/changed/failed/timeout/cut). Phone: behind one chip per reply.
- `ui/WhyLink.tsx` + `lib/why.ts` (pure): module → section (`preset` routing → Routing; otherwise Tools with `render_*`/`show_*` rows highlighted).
- `ui/ConfirmationPlacement.tsx`: the thread's pending confirmations (`usePendingConfirms` via `useConfirmation`) rendered in place after the latest exchange; prompt kind shows actions as command chips sending `action`.
- `ui/DeliveryFailedRow.tsx`: when the turn is `failed`, the row "Ze did not answer" with Resend (resends `lastSent` with its context and attachments through `useSendTurn`, keeping the original user line).
- `ui/ReplyThumbs.tsx`: compact thumbs on the latest reply (`features/reply-feedback`).
- `ui/RetryControl.tsx`: on the latest reply, `features/retry-reply` two-step consent; disabled with its reason when history is unavailable; notices from `lastOutcome`.
- `ui/AskOverlay.tsx` (moved): 183 shell behaviour unchanged (thread = selected session, Open in Ask, New chat, outbox, which now carries `workspacePlaced`), sends the outbox with `useSendTurn` passing the outbox context explicitly, body = `Canvas compact` + `ConfirmationPlacement` + `RetryControl`.
- `model/useAssemble.ts`: joins the conversation store, trace store and feedback for one thread.
- Screen context (195): the canvas publishes `canvas` refs (`index`, `type`, `ref` from `claim`) and `focused_module`; every module with a `claim` gets `ChatAboutChip`; `onChatAbout` comes in by prop.

### Trace instruments (US8)

Sources: the committed `WsTraceUpdateFrame` for the reply (REST hydration or the final frame) and, while streaming, the thread's `pendingTrace` plus `pendingArrivals`. Each instrument has a pure layout function in `widgets/assemble/lib/instruments/` (tested without the DOM) and a view in `widgets/assemble/ui/trace/`. Views use `shared/ui/hud` (`Meter`, `DotMatrix`, `Spark`, `Corners`) and SVG with ze.css tokens. Every value is also given as text (`aria-label` or a visible readout).

- `lib/instruments/signal.ts`: `stagesFor(trace, pending, arrivals, sentAt)` returns the drawn stages, each with a state (`lit` or `waiting`) and an arrival offset. The stages are route (routing fields set), screen (only when `screen` is set), memory (`memory_chunks` non-empty), tier (`tier` set), tools (count of tool calls) and reply (final committed). `sentAt` comes from the conversation store (`lastSent.at`, added in T002). Settled: every drawn stage is lit, plus `total_duration_ms`. `SignalPath.tsx`: a hairline strip that starts at a cream origin point (the monad) and has one tick per stage, with a mono "+1.2 s" under each lit tick. While streaming, light sweeps to the newest lit tick (off with reduced motion). Settled, it shows the dot-matrix total.
- `lib/instruments/routing.ts`: confidence and runner-up (`confidence − score_gap`, clamped at 0); method words (`embedding`, `haiku`, `fallback`, `screen`, `open_query`, `preset`, `forced`); the routing judgment's option probabilities, sorted; the tier row. `RoutingInstrument.tsx`: the bar with its ghost runner-up, needles per option with the chosen one cream, the tier line ("full · System One · <model>"), and the coordinate readout "Asked from · Doing › goal" / "Asked about · <subject>".
- `lib/instruments/memory.ts`: points `{x: score, y: extraction_confidence ?? null, glyph by source, text}`, ranked by `score × (confidence ?? 0.5)` for the list. `MemoryConstellation.tsx`: a 0–1 by 0–1 SVG plot, null-confidence points on a dashed floor line, hover or focus shows the text, arrow keys move between points. Phones get the ranked list.
- `lib/instruments/tools.ts`: lanes by `agent` (null → the reply's agent), calls in `call_index` order, `x` = cumulative duration of the earlier calls, `w` = `duration_ms` (minimum width for 0 ms), marks for `reversibility == irreversible`, `gate`, failure; write confirmations as ticks at their call. Partial calls (from `pendingTrace`) have no width and read "returned". `ToolsTimeline.tsx`: lanes with the caption "order and duration; start times not recorded".
- `lib/instruments/judgments.ts`: a closed map from question id to `{surface, label}`; rows grouped by surface; Choice → sorted probabilities with the answer; Noul → yes probability; Score → value; consumed, or skipped with the reason in words; `intake_outcome` parsed as `kind:reason[:link]` into words (the seven `OutcomeKind` values in `ze_worldstate/commitment_judge.py`). `JudgmentGauges.tsx`.
- `lib/instruments/readouts.ts`: total ms; main model (`tier.model`, else "not recorded"); System One count, summed `latency_ms` and summed `input_tokens`; compaction span; resume recap. `Readouts.tsx` uses `DotMatrix` for the total.
- `ReversalTrack.tsx`: `rollback.entries` in reverse `call_index` order, each with its effect phrase, undo tool and outcome in words, plus the message's rollback state.
- `TraceModule.tsx`: the rail. Head: "trace", feedback thumbs, coordinate readout. Body: `SignalPath`, then one collapsed line per instrument (its main readout), expanding on hover, focus or click; then the readout rows (Skills, Sources, Workspace, Conductor, Confirmations, Screen resolvers). `TraceSheet.tsx` puts the same rail in the HUD `Dialog` for the overlay's "Why?" and for phones.

### Displaced window

- `shared/api/ws-client.ts`: export `takeOver()`, which sets `displaced: false`, resets the retry delay and connects even when the document is hidden. The focus takeover stays.
- `widgets/app-shell/ui/DisplacedNotice.tsx`, shown by `AppShell` on every place while `displaced`: "Ze is open in another window" and a "Use here" `.ctl` calling `takeOver()`. The Ask bar takes a `disabledReason` prop, which `AppShell` sets to that line while displaced. Presence stays idle.

### `widgets/sessions-rail`, `widgets/try-chips`

- Sessions: `listSessions`, `searchSessions` (port of `SessionList`), thinking/attention dots from `useWsStore`, select → `useSession.setThread`, New chat → `newSession()`.
- Try chips (keys 1–3 when the Ask bar is empty and not focused): "What's slipping?" (`compose: "slipping"`), "What should I decide today?" (`decisions`), "How is <goal> going?" (`topic` = the active goal with the latest `last_progress_at` from `useGoalsQuery`, 184; hidden when there is none; the snapshot holds only stuck goals). Each calls the `onSend` prop; the page wires it to `useSendTurn` with `origin: "preset"`.

### `pages/ask`

Desktop: left rail (Presence compact, Try, Sessions, disclosure), canvas centre, trace module right for the selected reply. Phone: Presence compact → Try → canvas → trace chip. The Ask bar stays prop-driven: `AppShell` renders it everywhere and supplies `onSubmit(text, explicitContext, workspacePlaced)`: on `/ask` it calls `useSendTurn` on the selected thread, elsewhere it queues the overlay outbox (183). The bar gains the attach control (paperclip → `placeWorkspaceFile` from `entities/workspace` → chips; failure notice "Could not place the file in the workspace."; chips clear after a successful submit). 195's composer subject chip and suggestions render above it. `ask/:threadId` selects that thread. Onboarding: `start_if_needed` re-sends the view on every connect until it completes, so the page selects `onboarding:<session_id>` once per session id (remembered in memory and `localStorage`), and never when the URL names a thread (`/ask/:threadId`), the bar has text, or a turn is running; otherwise it shows a "Continue getting to know you" link in the rail.

### `@myguyze/ze-ui`

`PrimitiveRenderer` atoms move from utility classes to the system classes exported by ze-web's `ze.css` (`.lbl`, `.mono`, `.chip`, `.ctl`, `.meter`, `.card`), passed through a `classNames` map in `PrimitiveRendererContext` so the package carries no app CSS; defaults stay for other hosts. Text variants: `heading` → large mono value, `label` → `.lbl`, `muted` → dim. `progress` → `Meter`-style bar. 184's `headline` → dot-matrix headline via a `renderHeadline` slot (ze-web passes `DotMatrix`); `claim_card` and `claim_timeline` get HUD layouts. Charts keep the existing chart components with token colours.

### Hard cuts

`widgets/chat-workspace/**`, `features/chat-side-panel`, `features/load-chat-history`, `pages/chat`, `pages/ask/ui/AskInterim.tsx` (+ tests), `shared/effects/{background-beams,glowing-stars,spotlight}.tsx`, `shared/ui/layout/ChatShell.tsx` (+ export), `pages/jarvis/model/compose.ts`, `pages/jarvis/views/AssembleView.tsx` and its route, usePresence's frame handlers, "Ze's Mind" strings. `rtk proxy grep -rn "compose.ts\|composeAnswer\|chat-workspace\|Ze's Mind" apps/ze-web/src` empty (SC-002).

## Project Structure

### Documentation (this feature)

```
specs/phases/187-web-ask-assemble/
├── spec.md
├── plan.md
└── tasks.md
```

### Source Code

```
apps/ze-web/src/entities/conversation/{model/{store,reducer}.ts,api/useThreadHistory.ts,index.ts}
apps/ze-web/src/features/turn-stream/{ui/TurnFrameHandler.tsx,model/watchdog.ts,api/useSendTurn.ts,index.ts}
apps/ze-web/src/widgets/assemble/{ui/{Canvas,TraceModule,TraceSheet,WhyLink,ConfirmationPlacement,RetryControl,AskOverlay}.tsx,ui/trace/{SignalPath,RoutingInstrument,MemoryConstellation,ToolsTimeline,JudgmentGauges,Readouts,ReversalTrack,rows/*}.tsx,lib/{why.ts,instruments/*.ts},model/useAssemble.ts,index.ts}
apps/ze-web/src/features/trace-state/model/useTraceStore.ts ; shared/api/ws-client.ts ; widgets/app-shell/ui/DisplacedNotice.tsx
apps/ze-web/src/widgets/{sessions-rail,try-chips}/
apps/ze-web/src/pages/ask/{ui/AskPage.tsx,index.ts}
apps/ze-web/src/entities/presence/model/usePresence.ts ; features/ask-bar/{ui/AskBar.tsx,model/ask-overlay.ts} ; widgets/app-shell/ui/AppShell.tsx ; app/router/routes.tsx ; widgets/onboarding-wizard/ui/OnboardingWizard.tsx
packages/ze-ui/src/react/{PrimitiveRenderer.tsx,context.tsx}
```

## Docs touched ([DOCS] tasks)

- `docs/frontend.md`: Ask/Assemble, conversation store and reducer, turn-stream handler, deleted chat workspace and side panel.
- `docs/native-interface.md`: which client slice handles each WS frame; confirmation placement; retry flow in the canvas.
- `packages/ze-ui/README.md`: `classNames` map and `renderHeadline` slot.
- `docs/features.md`: Ask as an assembled answer with its trace instruments; the displaced-window line.
- `DESIGN.md`: a "Trace instruments" entry under Components (rail, calm by default, what each instrument encodes, the no-invented-data rule).
- `docs/component-schema.json` unchanged (no wire change).
- `AGENTS.md`: phase row 187; Learned User Preferences line on chat chrome ("trace" panel → trace module); `specs/README.md` row 187.

## Complexity Tracking

| Item | Why |
|---|---|
| New per-thread store replacing hook state | The overlay and `/ask` must show one thread; per-instance state made frames parse twice and threads diverge (spec Clarifications). |
| Trace instruments in this phase | The user asked for them on the Ask screen. They are drawn from data already on the client, so they need no backend. Each is a pure layout function plus a view, which keeps the JR lane parallel to the ENG store and canvas work. |
| `classNames` map in ze-ui | Keeps app CSS out of the shared renderer while plugin screens and chat share one look. |

## Proposed follow-up: 187b Trace telemetry (not in this phase)

The instruments draw only what the trace carries. These backend gaps (ze-core `MessageTrace`, `turn.py`, ze-api schemas) block the richer readings the user described. They are proposed as phase 187b: backend first, then the instrument upgrades.

| Gap | Today | 187b change | Instrument upgrade |
|---|---|---|---|
| Stage progress | partial frames only after `embed_route`, `resolve_screen`, `fetch_context` (when chunks exist), `choose_tier`, tool ends | one `stage` partial per graph node end with server ms since turn start | full signal path (preprocess … memory write) with server ms |
| E5 shortlist | `RoutingEnvelope.raw_scores` in `routing_log` only | top-k `shortlist` `[{agent, score}]` on the trace and route partial | ranked bar fan with names |
| Calibrated bars | not on `JudgmentTrace` | `surface` and `bar` (the threshold `decide()` compared against) per judgment | needle past a threshold line; tier against `simple_max` |
| Main-model cost | `llm_cost_log` keyed by session | per-turn `cost {prompt_tokens, completion_tokens, cost_usd, calls}` from the cost ContextVar | tokens and cost dot-matrix readouts |
| Context fill | compaction span only | `context {tokens_used, window}` from the 112 check | context-window meter with the compaction mark |
| Tool timing | `duration_ms` only; live partial tools send `0` and `success: true` | `started_ms` offset per call; real duration and success on the partial | true gantt with parallel fan-out overlap |
