# Implementation Plan: Ask / Assemble (W3)

**Branch**: `187-web-ask-assemble` | **Date**: 2026-10-17 | **Spec**: [spec.md](./spec.md)

**Input**: spec.md (Clarifications 2026-10-17 are binding; revised after Gauge's review A-1..A-10), `main` at b9e62e7b, 184 floor at 9ca300d8 (claim primitives, preset send, `useCardActions`), the 195 plan (screen-context store, single send path, `chatAbout`), the 186 plan (posture table, Needs-you rows). DESIGN.md "Canvas", "Cascade", "Trace".

## Summary

Ask becomes the Assemble canvas. The core change is structural. Conversation state moves out of the per-instance `useChatWorkspace` hook into one per-thread store (`entities/conversation`) with a pure reducer. One frame handler mounted in the shell feeds it (`features/turn-stream`), so `/ask` and the overlay show the same thread, and every chat frame is parsed once. On top of that store, `widgets/assemble` renders each reply as a Sentence module plus one module per top-level component, cascading from the orb. It shows the trace as a module and places confirmations in place, in both `/ask` and the overlay. `@myguyze/ze-ui` atoms are restyled to the HUD system. `widgets/chat-workspace`, the side panel, the starfield and the `/jarvis` composition are deleted.

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
| `useTraceStore`, `useSessionTraces`, `useTraceSocket` | chat-workspace side panel, `MessageBubble`, `TraceContent` | Kept; read by `widgets/assemble` `TraceModule`. |
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
apps/ze-web/src/widgets/assemble/{ui/{Canvas,TraceModule,WhyLink,ConfirmationPlacement,RetryControl,AskOverlay}.tsx,ui/trace/*,lib/why.ts,model/useAssemble.ts,index.ts}
apps/ze-web/src/widgets/{sessions-rail,try-chips}/
apps/ze-web/src/pages/ask/{ui/AskPage.tsx,index.ts}
apps/ze-web/src/entities/presence/model/usePresence.ts ; features/ask-bar/{ui/AskBar.tsx,model/ask-overlay.ts} ; widgets/app-shell/ui/AppShell.tsx ; app/router/routes.tsx ; widgets/onboarding-wizard/ui/OnboardingWizard.tsx
packages/ze-ui/src/react/{PrimitiveRenderer.tsx,context.tsx}
```

## Docs touched ([DOCS] tasks)

- `docs/frontend.md`: Ask/Assemble, conversation store and reducer, turn-stream handler, deleted chat workspace and side panel.
- `docs/native-interface.md`: which client slice handles each WS frame; confirmation placement; retry flow in the canvas.
- `packages/ze-ui/README.md`: `classNames` map and `renderHeadline` slot.
- `docs/features.md`: Ask as an assembled answer with its trace.
- `docs/component-schema.json` unchanged (no wire change).
- `AGENTS.md`: phase row 187; Learned User Preferences line on chat chrome ("trace" panel → trace module); `specs/README.md` row 187.

## Complexity Tracking

| Item | Why |
|---|---|
| New per-thread store replacing hook state | The overlay and `/ask` must show one thread; per-instance state made frames parse twice and threads diverge (spec Clarifications). |
| `classNames` map in ze-ui | Keeps app CSS out of the shared renderer while plugin screens and chat share one look. |
