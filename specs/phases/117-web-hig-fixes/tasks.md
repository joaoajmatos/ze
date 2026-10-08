# Tasks: Web UI HIG Audit Fixes

**Input**: `specs/phases/117-web-hig-fixes/` (spec.md, plan.md, research.md, data-model.md, quickstart.md)
**Scope (2026-10-08)**: US1, US2+US7, US4, US5, US10 remainder, US3 nit, US9 AI-disclosure line only. Already done: US6, US11, FR-014, main part of US3. Deferred: US8. Split out: US9 feedback/retry.
**Tags**: every task is `[BE]` (apps/ze-api, Python) or `[WEB]` (apps/ze-web, FSD). The two blocks are independent. The [BE] block can ship alone, after phase 163, and the [WEB] block can ship alone, because the web watchdog guarantees US1 whichever backend path fails.
**Tests**: Required by Constitution Principle V. [WEB]: Vitest + RTL (`make test-web`, `bun run lint`). [BE]: pytest with mocked sockets/pools (`make test`, `make lint`).

## Format: `- [ ] Txxx [P?] [Story] [TAG] Description with file path`

---

# BLOCK A: [BE] backend (independently testable)

**Goal**: A failed or non-serializable send never silently kills delivery, every turn ends in a terminal frame, and error frames carry `thread_id`.
**Independent test**: `make test` for ze-api. All tests use a mocked `WebSocket` and mocked `invoke_raw_turn`. No web client needed.

## Phase B1: Delivery hardening (US1)

- [ ] T001 [US1] [BE] Add a failing test in `apps/ze-api/tests/api/test_ws_delivery.py`: when `ConnectionManager.send_frame` gets a payload whose `send_json` raises `TypeError` (non-serializable), `_ws` is NOT set to None and a later `push()` still delivers. Also assert a real transport error (`RuntimeError`/closed socket) still clears `_ws`.
- [ ] T002 [US1] [BE] Fix `ConnectionManager.push` and `send_frame` in `apps/ze-api/ze_api/api/websocket/connection.py:113-138`: only null `_ws` on transport errors (closed or disconnected socket). Serialization errors are logged with `get_logger` and the frame is dropped. Depends on T001.
- [ ] T003 [US1] [BE] Make the `trace_update` build in `apps/ze-api/ze_api/interface/native.py:108-122` JSON-safe (serialize the trace with the same encoder used for `save_trace`, or drop unserializable fields) so it cannot raise inside the send path. Add a test in `apps/ze-api/tests/interface/` with a trace containing a non-JSON value. Depends on T002.
- [ ] T004 [US1] [BE] Add a test in `apps/ze-api/tests/api/test_ws_delivery.py` that the assistant reply frame is still delivered after a failed `trace_update` send on the same turn (regression for the "stored but not delivered" symptom).

## Phase B2: Terminal frame and tagged errors (US1)

- [ ] T005 [P] [US1] [BE] Add a failing test in `apps/ze-api/tests/api/test_ws.py`: when `invoke_raw_turn` returns an outcome with an empty/None `response` and not interrupted, the client receives an `error` (or equivalent terminal) frame tagged with the thread_id and the thread's busy slot is released.
- [ ] T006 [US1] [BE] Add the missing `else` branch in `apps/ze-api/ze_api/api/websocket/turns.py` after the `if outcome.response:` block (`:122`): send `{"type":"error","detail":...}` via `conn_mgr.send_frame(..., thread_id)` and log the turn outcome. Depends on T005.
- [ ] T007 [P] [US1] [BE] Add a failing test in `apps/ze-api/tests/api/test_ws.py`: a `message` frame without `thread_id` yields an `error` frame, and the busy-rejection and invoke-failure error frames carry `thread_id` when one is known.
- [ ] T008 [US1] [BE] In `apps/ze-api/ze_api/api/websocket/endpoint.py:199-203` keep the "thread_id required" error but echo any `thread_id` field present in the request. Confirm every `error` frame emitted in `endpoint.py`/`turns.py` passes `thread_id` when known. `WsErrorFrame.thread_id` already exists (`schemas.py:686`), so no schema or client change. Depends on T007.
- [ ] T009 [US1] [BE] Add a test in `apps/ze-api/tests/api/test_ws_conformance.py` that every emitted `error` frame validates against `WsErrorFrame`.

**Checkpoint A**: `make test` and `make lint` green. [BE] block mergeable on its own.

---

# BLOCK B: [WEB] apps/ze-web

## Phase W1: US1 chat always resolves (P1)

**Goal**: Every sent message ends in a visible reply or a visible retry state within a bounded wait, without reload.
**Independent test**: with a mocked WS that never answers, the composer unlocks into a retry state after the bound. With a dropped socket, thinking clears.

- [ ] T010 [US1] [WEB] Add `useChatWorkspace` tests in `apps/ze-web/src/widgets/chat-workspace/model/useChatWorkspace.test.ts` (new) with fake timers: (a) no reply within the bound, so history is re-fetched; (b) reply found in history, so thinking clears and the message shows; (c) still nothing, so a `deliveryFailed` state is exposed; (d) `retry()` re-sends or re-checks.
- [ ] T011 [US1] [WEB] Implement the watchdog in `apps/ze-web/src/widgets/chat-workspace/model/useChatWorkspace.ts` (set at `:219`/`:194`): start a bounded timer on send; on expiry call `useMessages().reload()` (`features/load-chat-history/api/useMessages.ts`, already exported but not used here). If a new assistant message appeared, call `stopThinking`. Otherwise set `deliveryFailed` and clear thinking. Expose `deliveryFailed` and `retry`. Reset on message/error frames. Pick the bound from an existing constant or add one in the same file (suggest 120s, configurable; spec assumption: match normal response time). Depends on T010.
- [ ] T012 [US1] [WEB] Render the failed state: a "Something went wrong. Retry" row in `apps/ze-web/src/entities/message/ui/ChatMessageList.tsx` driven by a new optional prop, wired in `widgets/chat-workspace/ui/ChatWorkspace.tsx` and `widgets/app-shell/ui/ContextOverlay.tsx`. Add a test in `ChatMessageList.test.tsx` (new). Depends on T011.
- [ ] T013 [US1] [WEB] In `apps/ze-web/src/shared/api/ws-client.ts` `onclose` (`:83`) clear thinking and typing-text for all threads and mark `isConnected=false` (clears the half-open case once the browser notices). Add a test in `shared/api/ws-client.test.ts`. Pong-timeout detection: if no frame (including `pong`) arrives within 2x ping interval, call `ws.close()`.
- [ ] T014 [US1] [WEB] Replace the blanket clear at `ws-client.ts:69` (`onopen`): do not wipe `thinkingThreads`. Instead, let the watchdog and history reconcile decide per thread. Add a test that a reconnect mid-turn keeps the composer locked until history resolves. Depends on T011.
- [ ] T015 [US1] [WEB] Fix the ephemeral send in `useChatWorkspace.ts:189`: include `thread_id: threadId` (the server rejects thread-less frames). Make the `error` handler (`:165-174`) ignore error frames whose `thread_id` is null when this hook did not send. Update/add tests in `useChatWorkspace.test.ts`. Pairs with T008 but is independently testable with a mocked `send`.

## Phase W2: US2 + US7 md-width nav reachability and accessible names (P1)

**Goal**: Every nav destination is reachable at md width and every icon-only control has an accessible name.
**Independent test**: render `NavGroup`/`AppShell` at md width; clicking a group icon opens a flyout listing all children; every control has an accessible name.

- [ ] T016 [US2] [WEB] Add tests in `apps/ze-web/src/widgets/app-shell/ui/NavGroup.test.tsx` (new): group button has accessible name = group label; clicking opens a flyout containing all child links; Escape and outside click close it; active child marks the group active.
- [ ] T017 [US2] [WEB] Implement the md click flyout in `apps/ze-web/src/widgets/app-shell/ui/NavGroup.tsx`: below `lg`, render children in an absolutely-positioned popover anchored to the group button (children currently sit in `hidden lg:grid`, `:120`). Keep the inline accordion at `lg+`. Make sure the sidebar `overflow-y-auto` container (`AppShell.tsx:66`) does not clip it (portal or `fixed` positioning). Depends on T016.
- [ ] T018 [US7] [WEB] Add `aria-label={label}` and `title={label}` to the group button and `href` NavLink in `NavGroup.tsx:56,80`, and to the Settings link in `AppShell.tsx:130-133`. Add `aria-expanded`/`aria-haspopup` on the group button. Depends on T016.
- [ ] T019 [US2] [WEB] Active indication at md (US2 AC3): when a child route is active, show the group icon with the active pill (`bg-plum-voltage/15`) in `NavGroup.tsx:85-88`, not only a text color change. Covered by T016. Depends on T017.

## Phase W3: US5 and US4 contextual panel (P2)

- [ ] T020 [US3] [WEB] Replace the desktop "Collapse" chevron with an X icon and label "Close" in `apps/ze-web/src/widgets/app-shell/ui/ContextOverlay.tsx:264-272` (US3 nit). Update the test in `ContextOverlay.test.tsx` (new, shared with T021).
- [ ] T021 [US5] [WEB] Add tests in `apps/ze-web/src/widgets/app-shell/ui/ContextOverlay.test.tsx` (new): at routes `/memory`, `/data`, `/settings`, `/goals` the panel label derives from the route; ⌘K and launcher give the same label; a registered override (entity or detail screen) still wins.
- [ ] T022 [US5] [WEB] Derive the screen label from `useLocation()` in `ContextOverlay.tsx` (reuse the route-label lookup logic in `shared/ui/layout/TopBar.tsx:10-27`, moved to `shared/config/nav-routes.ts` as `getRouteLabel(pathname)` so both use it). Keep `FloatingButton`'s `setScreen` as an optional override for entity-scoped context (`entityId`). Remove the unmount reset to `"chat"` (`FloatingButton.tsx:15`). Depends on T021.
- [ ] T023 [US4] [WEB] Stop the mobile launcher covering row actions: in `AppShell.tsx:143` raise bottom padding of the scroll container on mobile (`pb-28`), and/or move `FloatingButton` (`features/open-context-overlay/ui/FloatingButton.tsx:23`) so it clears the bottom bar and list content. Add a RTL class assertion test. Manually check on Goals, Workflows and Usage at 390px per `quickstart.md`.

## Phase W4: US10 remainder, US9 disclosure (P3/P4)

- [ ] T024 [P] [US10] [WEB] Raise the mobile bottom-nav label from `text-[10px]` to at least `text-[11px]` (target `text-xs`) in `apps/ze-web/src/widgets/app-shell/ui/AppShell.tsx:30`, and verify 8 items still fit at 390px.
- [ ] T025 [P] [US10] [WEB] Enlarge the breadcrumb back-button hit target to at least 44px in `apps/ze-web/src/shared/ui/layout/TopBar.tsx:49` (`min-h-11`, keep visual size). Add a test in `TopBar.test.tsx` (new).
- [ ] T026 [P] [US9] [WEB] Add a static, unobtrusive "Ze is AI and can make mistakes." line under the composer in `apps/ze-web/src/entities/message/ui/ChatInput.tsx` (shared by chat and overlay) and in the empty state in `widgets/chat-workspace/ui/ChatWorkspace.tsx`. Add a test in `ChatInput.test.tsx` (new). No feedback or retry UI (future phase).

**Checkpoint B**: `make test-web`, `bun run lint`, quickstart manual pass at 390 / 800 / 1280px.

---

# Cross-cutting [WEB]/[BE]

- [ ] T027 [WEB] Run `make test-web` and `bun run lint` and record results in the spec's implementation status.
- [ ] T028 [BE] Run `make test` and `make lint`; add one eval/manual scenario note to `quickstart.md`: send a message, kill the socket mid-turn, confirm recovery.
- [ ] T029 [WEB] Update `specs/phases/117-web-hig-fixes/spec.md` status to `Implemented` when T001-T028 are checked, using companion `write-context.py --append` then `--materialize` (never hand-edit checkboxes), and run the speckit after-implement hook.
- [ ] T030 [WEB] Open a stub spec entry in `specs/README.md` for the split-out "Assistant response feedback and retry" phase (US9 remainder) so it is not lost. No spec files beyond the index line.

---

## Dependencies and parallelism

- Block A and Block B are fully independent. B can ship first. A is picked up after 163.
- A: T001→T002→T003/T004; T005→T006; T007→T008→T009. T005/T007 run in parallel with T001.
- B: T010→T011→T012/T014; T013 and T015 parallel to T011; T016→T017→T019, T018 after T016; T021→T022; T020, T023, T024, T025, T026 are parallel, different files.
- Hot files: `useChatWorkspace.ts` (T011, T015), `NavGroup.tsx` (T017, T018, T019), `AppShell.tsx` (T018, T023, T024), `ContextOverlay.tsx` (T012, T020, T022). Sequence edits within each file.

## Strategy

MVP = Block B Phase W1 (US1 client recovery) + W2 (nav). Then A for the root-cause fix. Then W3, W4.
